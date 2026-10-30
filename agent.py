# agent.py - Job Scout: an AI agent that uses HireOps tools to find and shortlist jobs
"""How an agent works.

The model gets a goal and a list of tools. Each turn it either asks for a tool
(a name plus arguments) or gives its final answer. Our code runs the tool, hands
the result back, and asks again. The model decides what to do next; the code stays
in charge of what is allowed: only listed tools, checked arguments, a step limit,
a token budget, and a person's yes before anything is saved.
"""

import argparse
import json
import logging
import re
from dataclasses import dataclass, field

import httpx  # its error types tell us when the model was too slow
import requests  # its error types tell us when a job board didn't answer
from pydantic import BaseModel, Field, ValidationError

import ai
from matcher import match
from radar import FETCHERS, load_json, title_fits

logger = logging.getLogger(__name__)

MAX_STEPS = 8  # most model turns in one run; stops an agent that goes in circles
TOKEN_BUDGET = 30000  # most word-pieces (read + written) one run may use
# Longer tool results are cut, so the model's memory (its context) stays small
MAX_RESULT_CHARS = 2500

# The system message: standing instructions the model reads before the goal
SYSTEM = """You are Job Scout, a careful job-search assistant for one person.
Use the tools to reach the goal. Rules:
- Job IDs come from find_jobs. Call find_jobs before read_job, score_job or save_job.
- Only mention jobs and job IDs that a tool returned to you. Never make one up.
- Use save_job only when the goal asks you to shortlist or save a job.
- If a tool returns an error, fix your request or explain the problem.
- Call ONE tool per turn and wait for its result. Never guess a job ID.
- Scores come only from score_job (0-100). Never write a score yourself.
- Call list_shortlist to see jobs the person already saved. Don't suggest or save those again.
- Finish in under 150 words: for each job, its ID, title, company, score and one reason."""


# --- What each tool accepts. Pydantic checks the model's arguments against these. ---


class NoArgs(BaseModel):
    pass


class FindJobs(BaseModel):
    company: str = Field(
        description="A company name exactly as list_companies gives it"
    )


class JobId(BaseModel):
    job_id: str = Field(
        description="A job ID that find_jobs returned, e.g. greenhouse-123"
    )


class SaveJob(BaseModel):
    job_id: str = Field(description="A job ID that find_jobs returned")
    reason: str = Field(max_length=300, description="One sentence: why this job fits")


# Every tool the agent may use: name -> (its arguments, what it does).
# The model sees ONLY these. A name that isn't here is refused.
SPECS = {
    "list_companies": (NoArgs, "List the target companies Job Scout can search."),
    "find_jobs": (
        FindJobs,
        "Open jobs at one company whose titles fit the person's target titles.",
    ),
    "read_job": (
        JobId,
        "The title, company, place and start of one job's description.",
    ),
    "score_job": (
        JobId,
        (
            "How well the person's resume matches one job: a 0-100 score, "
            "the skills shown and the skills missing."
        ),
    ),
    "save_job": (
        SaveJob,
        "Save one job to the person's shortlist. The person must say yes first.",
    ),
    "list_shortlist": (
        NoArgs,
        "The jobs the person has already saved to their shortlist.",
    ),
}


def tool_schemas():
    """The tool list in the shape Ollama expects: name, description, JSON arguments."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": shape.model_json_schema(),
            },
        }
        for name, (shape, description) in SPECS.items()
    ]


class ToolError(Exception):
    """A tool was asked for something it can't do; the message goes back to the model."""


class Tools:
    """The tools themselves. Each method takes checked arguments and returns plain data."""

    def __init__(
        self, config, resume_text, skills, approve, shortlist_file="shortlist.json", fetch_jobs=None
    ):
        self.config = config  # radar_config.json: companies, titles, exclude
        self.resume_text = resume_text
        self.skills = skills  # skills.json, for the rules-only score
        self.approve = approve  # a function that asks the person yes or no
        self.shortlist_file = shortlist_file
        self.fetch_jobs = fetch_jobs  # None = the live job boards; the eval passes a sample
        # Every job a tool has returned, by ID. These are the only facts the agent has.
        self.jobs = {}
        # IDs list_shortlist returned. Kept apart from self.jobs: saved jobs have no
        # description, so read_job and score_job can't use them.
        self.saved_ids = set()

    def company_names(self):
        """The target company names, for list_companies and find_jobs' error."""
        return [company["name"] for company in self.config["companies"]]

    def list_companies(self, args):
        # A next step inside the result, like find_jobs: without it the model
        # sometimes answers with a tool name instead of these names. It doesn't
        # mention find_jobs: that sent off-topic questions to a job search.
        return {
            "companies": self.company_names(),
            "next": "Answer the person with these names.",
        }

    def find_jobs(self, args):
        # next(...) gives the first company with that name, or None if there's none
        wanted = args.company.strip().lower()
        company = next(
            (c for c in self.config["companies"] if c["name"].lower() == wanted), None
        )
        if company is None:
            # The real names and a next step go inside the error: this small model
            # follows a hint in a tool result better than a rule in the prompt
            names = ", ".join(self.company_names())
            raise ToolError(
                f"No company called {args.company!r}. The person's companies are: "
                f"{names}. Don't call find_jobs for it again. "
                "Tell the person it isn't on their list."
            )
        if self.fetch_jobs:  # the eval: a fixed sample, so every run sees the same jobs
            found = self.fetch_jobs(company["name"])
        else:
            fetch = FETCHERS[company["board"]]
            found = fetch(company["name"], company["slug"])
        titles, exclude = self.config["titles"], self.config["exclude"]
        fits = [job for job in found if title_fits(job, titles, exclude)]
        for job in fits:
            self.jobs[job["id"]] = job  # remember it, so later tools can use the ID
        # [:15] keeps the answer short; the model only needs IDs, titles and places
        jobs = [
            {"id": j["id"], "title": j["title"], "location": j["location"]}
            for j in fits[:15]
        ]
        # A next step inside the result: small models follow this better than the prompt
        return {"jobs": jobs, "next": "To compare jobs, call score_job for each id, one at a time."}

    def job(self, job_id):
        """The job with this ID, if a tool returned it earlier in this run."""
        if job_id not in self.jobs:
            raise ToolError(
                f"Unknown job ID {job_id!r}. Use an ID that find_jobs returned."
            )
        return self.jobs[job_id]

    def read_job(self, args):
        job = self.job(args.job_id)
        return {
            "id": job["id"],
            "title": job["title"],
            "company": job["company"],
            "location": job["location"],
            "description": job["description"][:1500],
        }

    def score_job(self, args):
        job = self.job(args.job_id)
        # The same rules-only match as Job Radar: no AI here, so the score can be trusted
        result = match(job["description"], self.resume_text, self.skills)
        return {
            "id": job["id"],
            "score": result.score(),
            "have": result.have,
            "missing": result.missing()[:5],
        }

    def save_job(self, args):
        job = self.job(args.job_id)
        question = f"Save '{job['title']}' at {job['company']}? Reason: {args.reason}"
        if not self.approve(question):  # the person said no: nothing is written
            return {
                "saved": False,
                "note": "The person said no. Don't ask again for this job.",
            }
        shortlist = load_shortlist(self.shortlist_file)
        shortlist.append(
            {
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "url": job["url"],
                "reason": args.reason,
            }
        )
        with open(self.shortlist_file, "w") as f:
            json.dump(shortlist, f, indent=2)
        return {"saved": True}

    def list_shortlist(self, args):
        # Read-only: it never writes, so it doesn't need approve()
        saved = load_shortlist(self.shortlist_file)
        self.saved_ids.update(job["id"] for job in saved)
        # Only the short fields, so a long shortlist isn't cut off
        return [
            {"id": j["id"], "company": j["company"], "title": j["title"]}
            for j in saved
        ]


def load_shortlist(path):
    """Jobs saved so far; an empty list before the first save."""
    try:
        return load_json(path)
    except FileNotFoundError:
        return []


def run_tool(tools, name, raw_args):
    """Run one tool the model asked for. Always returns text, never crashes the run.

    Errors go back to the model as text, so it can correct itself.
    """
    if name not in SPECS:
        return (
            f"Error: there is no tool called {name!r}. Use one of: {', '.join(SPECS)}."
        )
    shape, _ = SPECS[name]
    try:
        args = shape.model_validate(raw_args or {})  # check the arguments
    except ValidationError as error:
        problem = error.errors()[0]
        place = ".".join(str(part) for part in problem["loc"]) or "arguments"
        return f"Error: bad arguments for {name}: {place}: {problem['msg']}"
    try:
        result = getattr(tools, name)(args)  # getattr finds the method with this name
    except ToolError as error:
        return f"Error: {error}"
    except requests.RequestException as error:
        return f"Error: the job board didn't answer ({error.__class__.__name__})."
    text = json.dumps(result)
    if len(text) > MAX_RESULT_CHARS:
        text = text[:MAX_RESULT_CHARS] + " ...(cut)"
    return text


# Job IDs look like greenhouse-123, lever-<letters and numbers> or ashby-<id>
JOB_ID = re.compile(r"\b(?:greenhouse|lever|ashby)-[0-9A-Za-z-]+")


def check_answer(answer, tools):
    """Warnings for any job ID in the final answer that no tool returned (invented)."""
    return [
        f"The answer mentions {job_id}, which no tool returned. Don't trust that line."
        for job_id in sorted(set(JOB_ID.findall(answer)))
        if job_id not in tools.jobs and job_id not in tools.saved_ids
    ]

# A score written in the answer, like "Score: 92", "score 8/10" or
# "The score for the selected job is 92". [^.\n\d]{0,60} allows up to 60 characters
# between the word and the number, but never a period or a new line, so the check
# stays inside one sentence or list line.
SCORE = re.compile(r"\bscored?\b[^.\n\d]{0,60}\d", re.IGNORECASE)
# "Best match", "top fit", "matches your resume best": picking a job is a judgment
# that needs scores, even when the answer shows no number
PICKS = re.compile(
    r"\b(?:best|top|strongest|closest)\b[^.\n]{0,40}?\b(?:match|matches|fit|fits)\b"
    r"|\bmatches your resume\b",
    re.IGNORECASE,
)
MAX_CORRECTIONS = 2  # most times one run may send an answer back to the model
# "I'll call score_job", "Let me use find_jobs"...: a promise to call, not a call.
# Plain mentions ("Call list_companies for the names") don't count.
ANNOUNCED = re.compile(
    r"\b(?:I'll|I will|let me|I need to|I'm going to|I am going to)\b[^.\n]{0,60}?"
    r"\b(" + "|".join(SPECS) + r")\b",
    re.IGNORECASE,
)
# A tool call typed as text, like find_jobs(["Datadog"]) or {"name": "find_jobs", ...}
TYPED_CALL = re.compile(
    r"\b(?:" + "|".join(SPECS) + r")\s*\(|\"name\":\s*\"(?:" + "|".join(SPECS) + r")\""
)
# An answer that is only a tool name, like find_jobs or `find_jobs`.
# ^ and $ mean the whole answer; \W* allows quotes, backticks or a period around it.
BARE_TOOL = re.compile(r"^\W*(?:" + "|".join(SPECS) + r")\W*$")


def answer_problem(answer, run):
    """Why the final answer can't be accepted yet, or "" if it's fine.

    Scores must come from score_job. A score in the answer with no successful
    score_job call means the model made the number up.
    """
    scored = any(
        s["tool"] == "score_job" and not s["result"].startswith("Error")
        for s in run.steps
    )
    # Job IDs have digits too ("scored greenhouse-123"), so take them out first
    if SCORE.search(JOB_ID.sub("", answer)) and not scored:
        return (
            "Your answer shows scores, but you never called score_job. "
            "Call score_job for each job ID you mention, then answer again."
        )
    if PICKS.search(answer) and not scored:
        return (
            "Your answer picks a best job, but you never called score_job. "
            "Call score_job for the jobs you found, then answer again."
        )
    # The model typed a tool call (or just a tool's name) as text instead of calling it
    if TYPED_CALL.search(answer) or BARE_TOOL.match(answer):
        return (
            "You typed a tool call as text. To use a tool, call it. "
            "Otherwise answer the person in plain words."
        )
    # The model announced a call instead of making it ("First, I'll call score_job")
    announced = ANNOUNCED.search(answer)
    if announced:
        return (
            f"You said you would use {announced.group(1)} but didn't call it. "
            "Call it now, or give your final answer."
        )
    return ""

@dataclass
class Run:
    """What one agent run did: its answer, every tool call, and why it stopped."""

    answer: str = ""
    steps: list = field(default_factory=list)  # one dict per tool call: the trace
    stopped: str = ""  # why it stopped early, if it did
    warnings: list = field(default_factory=list)
    tokens: int = 0  # word-pieces read + written in this run
    corrections: int = 0  # answers sent back to the model to fix    


def say_nothing(message):
    """The default progress function: it ignores the message."""


def run_agent(goal, tools, client=None, progress=say_nothing):
    """Work on `goal` with the tools until the model answers or a limit is reached.

    client is the connection to Ollama; tests pass a fake one that never calls a model.
    """
    client = client or ai.client
    run = Run()
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": goal},
    ]
    for step in range(1, MAX_STEPS + 1):
        if run.tokens > TOKEN_BUDGET:
            run.stopped = f"it used up the token budget of {TOKEN_BUDGET}"
            return run
        try:
            response = client.chat(
                model=ai.MODEL,
                messages=messages,
                tools=tool_schemas(),
                options={
                    "temperature": 0,
                    "num_predict": ai.MAX_TOKENS,
                    "num_ctx": ai.CONTEXT,
                },
            )
        except httpx.TimeoutException:
            run.stopped = f"{ai.MODEL} took longer than {ai.TIMEOUT} seconds"
            return run
        except ConnectionError:
            run.stopped = "Ollama isn't running (open the Ollama app and try again)"
            return run
        usage = ai.record_usage("agent", response, 1)
        run.tokens += usage.prompt_tokens + usage.output_tokens

        message = response.message
        calls = message.tool_calls or []
        if not calls:  # no tool asked for: this is the final answer
            answer = (message.content or "").strip()
            problem = answer_problem(answer, run)
            if problem and run.corrections < MAX_CORRECTIONS:
                # Guardrail: send a made-up answer back instead of accepting it
                run.corrections += 1
                progress(f"  step {step}: answer sent back: {problem}")
                logger.info("agent_correction %s", json.dumps({"step": step}))
                messages.append(message)
                messages.append({"role": "user", "content": problem})
                continue
            run.answer = answer
            run.warnings = check_answer(run.answer, tools)
            if problem:  # still wrong after every correction: accept it, but warn
                run.warnings.append(
                    f"Not fixed after {MAX_CORRECTIONS} tries: {problem}"
                )
            return run

        messages.append(message)  # the model's request stays in the conversation
        # Guardrail: one tool per turn. A small model often asks for find_jobs AND
        # score_job at once, guessing job IDs it hasn't seen yet. Only the first call
        # runs; the model sees its real result, then asks for the next tool.
        for call in calls[:1]:
            name = call.function.name
            args = dict(call.function.arguments or {})
            progress(f"  step {step}: {name} {json.dumps(args)}")
            result = run_tool(tools, name, args)
            if len(calls) > 1:
                result += " (Only one tool runs per turn. Ask for the next one now.)"
            run.steps.append(
                {"step": step, "tool": name, "args": args, "result": result[:200]}
            )
            # One JSON line per tool call in hireops.log: the trace of what the agent did
            logger.info(
                "agent_step %s",
                json.dumps(
                    {
                        "step": step,
                        "tool": name,
                        "args": args,
                        "ok": not result.startswith("Error"),
                    }
                ),
            )
            messages.append({"role": "tool", "content": result, "tool_name": name})

    run.stopped = f"it reached the limit of {MAX_STEPS} steps"
    return run


def ask_person(question):
    """Ask in the terminal; only a typed y counts as yes."""
    return input(f"\n{question} [y/N] ").strip().lower() == "y"


def main():
    parser = argparse.ArgumentParser(
        description="Job Scout: an AI agent that finds jobs."
    )
    parser.add_argument("goal", help='e.g. "Find SRE roles at Datadog and score them"')
    parser.add_argument("-r", "--resume", default="samples/resume.md", help="resume")
    args = parser.parse_args()

    logging.basicConfig(
        filename="hireops.log",
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    with open(args.resume) as f:
        resume_text = f.read()
    tools = Tools(
        load_json("radar_config.json"),
        resume_text,
        load_json("skills.json"),
        ask_person,
    )

    print(f"Job Scout ({ai.MODEL}) is working on: {args.goal}\n")
    run = run_agent(args.goal, tools, progress=print)
    if run.stopped:
        print(f"\nStopped early: {run.stopped}.")
    if run.answer:
        print(f"\n{run.answer}")
    for warning in run.warnings:
        print(f"\nWarning: {warning}")
    print(f"\n{len(run.steps)} tool calls, {run.tokens} tokens.")


if __name__ == "__main__":
    main()