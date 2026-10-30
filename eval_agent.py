# eval_agent.py - grade Job Scout on a fixed set of goals, with the REAL model.
# Unit tests (test_agent.py) prove the code's guardrails work. This eval measures the
# model: does it pick the right tools, avoid the wrong ones, and never invent a job?
# Run it after every change to the prompt, the tool descriptions or the model.
import json
import re
import time
from datetime import date
from pathlib import Path

import agent
from radar import load_json

# Every case reads this fixed shortlist, never the real shortlist.json: the real one
# is private and changes whenever a job is saved, so results would differ run to run
SAMPLE_SHORTLIST = "evals/sample_shortlist.json"
SAMPLE_JOBS = "evals/sample_jobs.json"


def never_approve(question):
    """During an eval nothing is saved: every save request gets an automatic no."""
    return False


def make_tools(config, resume_text, skills):
    """A fresh Tools for one case: the sample shortlist and the sample job board."""
    sample = load_json(SAMPLE_JOBS)
    return agent.Tools(
        config, resume_text, skills, never_approve,
        shortlist_file=SAMPLE_SHORTLIST,
        # lambda = a one-line function: given a company name, return its sample jobs
        fetch_jobs=lambda name: sample.get(name, []),
    )


def grade(case, run):
    """The reasons this run failed its case; an empty list means it passed.

    A must_call tool only counts if it WORKED: a call that came back with an error
    (like a made-up job ID) doesn't prove the model used the tool correctly.
    The trace is also graded as a sequence: must_call_in_order checks the order
    tools first worked in, and any guessed job ID fails the run.
    """
    worked = {s["tool"] for s in run.steps if not s["result"].startswith("Error")}
    tried = {step["tool"] for step in run.steps}
    problems = []
    for tool in case["must_call"]:
        if tool not in worked:
            problems.append(f"didn't call {tool} successfully")
    for tool in case["must_not_call"]:
        if tool in tried:
            problems.append(f"called {tool}, which it shouldn't")
    # Optional: words the answer must contain, ignoring upper/lower case.
    # .get(..., []) means a case without this list skips the check.
    for words in case.get("answer_must_include", []):
        if words.lower() not in run.answer.lower():
            problems.append(f"answer doesn't mention {words}")
    # Optional: tools that must first WORK in this order, e.g. find_jobs before
    # score_job. first_ok maps each tool to the step where it first worked;
    # setdefault keeps only the first one. Failed calls (errors) don't count.
    first_ok = {}
    for s in run.steps:
        if not s["result"].startswith("Error"):
            first_ok.setdefault(s["tool"], s["step"])
    wanted = case.get("must_call_in_order", [])
    # Tools that never worked are already reported by must_call, so skip them here
    order = [first_ok[tool] for tool in wanted if tool in first_ok]
    if order != sorted(order):
        problems.append("tools ran out of order: " + " before ".join(wanted))
    # Optional: the job passed to save_job must be the one with the highest score_job
    # result. scores maps job_id -> score for every successful score_job call; saved_id
    # is the first job the model tried to save (even if the person said no).
    if case.get("must_save_top_score"):
        scores = {}
        for s in run.steps:
            if s["tool"] == "score_job" and not s["result"].startswith("Error"):
                job_id = s.get("args", {}).get("job_id")
                # Results are cut at 200 characters, so json.loads would fail on a
                # long one. "score" comes right after "id", so it always survives.
                found = re.search(r'"score": (\d+)', s["result"])
                if job_id and found:
                    scores[job_id] = int(found.group(1))
        saved_id = None
        for s in run.steps:
            if s["tool"] == "save_job" and not s["result"].startswith("Error"):
                saved_id = s.get("args", {}).get("job_id")
                break
        if scores and saved_id:
            top_id = max(scores, key=lambda jid: scores[jid])
            if scores.get(saved_id) != scores[top_id]:
                problems.append(
                    f"saved {saved_id} (score {scores.get(saved_id, '?')}) "
                    f"but {top_id} had a higher score of {scores[top_id]}"
                )
    # A guessed job ID fails the run even if the model recovered afterwards.
    # Other errors (like a company that isn't on the list) can be correct behaviour.
    for s in run.steps:
        if "Unknown job ID" in s["result"]:
            problems.append(f"{s['tool']} tried a job ID no tool returned")
    # Optional: "score them" means more than one. Count the different jobs it scored.
    scored_ids = {
        s.get("args", {}).get("job_id")
        for s in run.steps
        if s["tool"] == "score_job" and not s["result"].startswith("Error")
    }
    need = case.get("must_score_at_least", 0)
    if len(scored_ids) < need:
        problems.append(f"scored only {len(scored_ids)} job(s); the case needs {need}")
    # Optional: the answer must name the job it asked to save, by its ID
    if case.get("must_name_saved_job"):
        for s in run.steps:
            if s["tool"] == "save_job" and not s["result"].startswith("Error"):
                job_id = s.get("args", {}).get("job_id", "")
                if job_id not in run.answer:
                    problems.append(f"answer doesn't name the saved job {job_id}")
    for warning in run.warnings:  # invented job IDs, answers not fixed in time
        problems.append(warning[:110])
    if run.stopped:
        problems.append(f"stopped early: {run.stopped}")
    if not run.answer:
        problems.append("gave no final answer")
    return problems


def main():
    cases = load_json("evals/agent_cases.json")
    with open("samples/resume.md") as f:
        resume_text = f.read()
    config, skills = load_json("radar_config.json"), load_json("skills.json")

    results = []
    for number, case in enumerate(cases, start=1):
        # A fresh Tools for every case, so one case's jobs can't help the next one
        tools = make_tools(config, resume_text, skills)
        started = time.time()
        run = agent.run_agent(case["goal"], tools)
        problems = grade(case, run)
        results.append(
            {
                "goal": case["goal"],
                "passed": not problems,
                "problems": problems,
                "tools": [step["tool"] for step in run.steps],
                # Calls that came back with an error, e.g. a made-up job ID
                "failed_calls": [
                    f"{s['tool']}: {s['result'][:80]}"
                    for s in run.steps
                    if s["result"].startswith("Error")
                ],
                "answer": run.answer,
                "tokens": run.tokens,
                "seconds": round(time.time() - started, 1),
            }
        )
        mark = "PASS" if not problems else "FAIL"
        print(f"{number}. {mark}  {case['goal']}")
        for problem in problems:
            print(f"         - {problem}")
        for failed in results[-1]["failed_calls"]:
            print(f"         (failed call) {failed}")

    passed = sum(result["passed"] for result in results)
    tokens = sum(result["tokens"] for result in results)
    print(
        f"\n{passed} of {len(results)} passed · {tokens} tokens · model {agent.ai.MODEL}"
    )

    # Keep every result, so you can compare runs before and after a change
    out = Path("evals") / f"results-{date.today()}.json"
    out.write_text(json.dumps({"model": agent.ai.MODEL, "results": results}, indent=2))
    print(f"Saved {out}")


if __name__ == "__main__":
    main()