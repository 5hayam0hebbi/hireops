# test_agent.py - tests for Job Scout. None of them call the AI or a job board:
# a FakeClient plays the model with scripted answers, and a fake board gives two jobs.
import json
from types import SimpleNamespace as NS  # a quick object with the fields we give it

import agent


def call(name, **args):
    """One tool request, shaped like Ollama's: call.function.name / .arguments."""
    return NS(function=NS(name=name, arguments=args))


def reply(content="", calls=None, tokens=100):
    """One model answer: either text (the final answer) or tool requests."""
    message = NS(role="assistant", content=content, tool_calls=calls)
    return NS(
        message=message, prompt_eval_count=tokens, eval_count=10, total_duration=0
    )


class FakeClient:
    """Plays the model: hands out the scripted replies in order."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.tool_results = []  # what our code sent back after each tool call

    def chat(self, model, messages, tools, options):
        self.tool_results = [
            m["content"]
            for m in messages
            if isinstance(m, dict) and m["role"] == "tool"
        ]
        return self.replies.pop(0)


JOB = {
    "id": "greenhouse-1",
    "company": "Datadog",
    "title": "Senior SRE",
    "location": "Toronto",
    "url": "https://example.com/1",
    "description": "We need Python, Terraform and Kubernetes.",
}
INTERN = {**JOB, "id": "greenhouse-2", "title": "SRE Intern"}  # excluded by title
CONFIG = {
    "companies": [{"name": "Datadog", "board": "greenhouse", "slug": "datadog"}],
    "titles": ["SRE"],
    "exclude": ["Intern"],
    "locations": ["Toronto"],
}


def make_tools(monkeypatch, tmp_path, approve=lambda question: True):
    monkeypatch.setitem(
        agent.FETCHERS, "greenhouse", lambda company, slug: [JOB, INTERN]
    )
    return agent.Tools(
        CONFIG,
        "Python and Terraform",
        ["Python", "Terraform", "Kubernetes"],
        approve,
        shortlist_file=tmp_path / "shortlist.json",
    )


def test_uses_a_tool_then_answers(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    client = FakeClient(
        [
            reply(calls=[call("find_jobs", company="Datadog")]),
            reply("greenhouse-1: Senior SRE at Datadog fits."),
        ]
    )
    run = agent.run_agent("Find SRE jobs at Datadog", tools, client=client)
    assert run.answer.startswith("greenhouse-1")
    assert [s["tool"] for s in run.steps] == ["find_jobs"]
    assert "greenhouse-2" not in tools.jobs  # the intern job was filtered out
    assert run.warnings == [] and run.stopped == ""


def test_unknown_tool_is_refused(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    client = FakeClient([reply(calls=[call("delete_everything")]), reply("Sorry.")])
    agent.run_agent("Clean up", tools, client=client)
    assert client.tool_results[0].startswith("Error: there is no tool called")


def test_bad_arguments_are_refused(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    client = FakeClient([reply(calls=[call("read_job")]), reply("I need a job ID.")])
    agent.run_agent("Read a job", tools, client=client)
    assert client.tool_results[0].startswith(
        "Error: bad arguments for read_job: job_id"
    )


def test_a_job_id_must_come_from_find_jobs(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    client = FakeClient(
        [reply(calls=[call("score_job", job_id="greenhouse-999")]), reply("No.")]
    )
    agent.run_agent("Score a job", tools, client=client)
    assert client.tool_results[0].startswith("Error: Unknown job ID")


def test_unknown_company(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    client = FakeClient(
        [reply(calls=[call("find_jobs", company="Acme")]), reply("No.")]
    )
    agent.run_agent("Jobs at Acme", tools, client=client)
    assert "The person's companies are: Datadog." in client.tool_results[0]
    assert "Don't call find_jobs for it again" in client.tool_results[0]


def test_score_uses_rules_not_ai(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    client = FakeClient(
        [
            reply(calls=[call("find_jobs", company="Datadog")]),
            reply(calls=[call("score_job", job_id="greenhouse-1")]),
            reply("Done."),
        ]
    )
    agent.run_agent("Score Datadog jobs", tools, client=client)
    score = json.loads(client.tool_results[1])
    assert score["score"] == 67  # 2 of 3 skills
    assert score["missing"] == ["Kubernetes"]


def test_stops_at_the_step_limit(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    looping = [reply(calls=[call("list_companies")])] * agent.MAX_STEPS
    run = agent.run_agent("Loop forever", tools, client=FakeClient(looping))
    assert "limit" in run.stopped
    assert len(run.steps) == agent.MAX_STEPS


def test_stops_at_the_token_budget(monkeypatch, tmp_path):
    monkeypatch.setattr(agent, "TOKEN_BUDGET", 150)
    tools = make_tools(monkeypatch, tmp_path)
    looping = [reply(calls=[call("list_companies")], tokens=100)] * agent.MAX_STEPS
    run = agent.run_agent("Loop", tools, client=FakeClient(looping))
    assert "token budget" in run.stopped
    assert len(run.steps) == 2  # 110 tokens, then 220: over 150, so it stops


def test_nothing_is_saved_without_a_yes(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path, approve=lambda question: False)
    client = FakeClient(
        [
            reply(calls=[call("find_jobs", company="Datadog")]),
            reply(
                calls=[call("save_job", job_id="greenhouse-1", reason="Strong SRE fit")]
            ),
            reply("Not saved."),
        ]
    )
    agent.run_agent("Shortlist the best Datadog job", tools, client=client)
    assert json.loads(client.tool_results[1])["saved"] is False
    assert not (tmp_path / "shortlist.json").exists()


def test_saves_after_a_yes(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    client = FakeClient(
        [
            reply(calls=[call("find_jobs", company="Datadog")]),
            reply(
                calls=[call("save_job", job_id="greenhouse-1", reason="Strong SRE fit")]
            ),
            reply("Saved greenhouse-1."),
        ]
    )
    agent.run_agent("Shortlist the best Datadog job", tools, client=client)
    saved = json.loads((tmp_path / "shortlist.json").read_text())
    assert [job["id"] for job in saved] == ["greenhouse-1"]


def test_invented_job_id_is_flagged(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    client = FakeClient([reply("Apply to greenhouse-777 today.")])
    run = agent.run_agent("Any jobs?", tools, client=client)
    assert run.warnings and "greenhouse-777" in run.warnings[0]


def test_ollama_not_running(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)

    class DownClient:
        def chat(self, **kwargs):
            raise ConnectionError("no Ollama")

    run = agent.run_agent("Any jobs?", tools, client=DownClient())
    assert "Ollama isn't running" in run.stopped

def test_only_one_tool_runs_per_turn(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    client = FakeClient(
        [
            reply(
                calls=[
                    call("find_jobs", company="Datadog"),
                    call("score_job", job_id="(job ID returned by find_jobs)"),
                ]
            ),
            reply("Found greenhouse-1."),
        ]
    )
    run = agent.run_agent("Find and score Datadog jobs", tools, client=client)
    assert [s["tool"] for s in run.steps] == ["find_jobs"]  # the guess never ran
    assert "Only one tool runs per turn" in client.tool_results[0]

def test_made_up_score_is_sent_back(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    client = FakeClient(
        [
            reply(calls=[call("find_jobs", company="Datadog")]),
            reply("greenhouse-1 Senior SRE, Score: 92"),  # made up: no score_job yet
            reply(calls=[call("score_job", job_id="greenhouse-1")]),
            reply("greenhouse-1 Senior SRE, Score: 67"),
        ]
    )
    run = agent.run_agent("Score Datadog jobs", tools, client=client)
    assert [s["tool"] for s in run.steps] == ["find_jobs", "score_job"]
    assert run.corrections == 1
    assert run.answer.endswith("Score: 67") and run.warnings == []


def test_made_up_score_after_every_correction_is_flagged(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    made_up = [reply("greenhouse-1 Senior SRE, Score: 92")] * 3
    client = FakeClient([reply(calls=[call("find_jobs", company="Datadog")])] + made_up)
    run = agent.run_agent("Score Datadog jobs", tools, client=client)
    assert run.corrections == agent.MAX_CORRECTIONS
    assert "never called score_job" in run.warnings[-1]


def test_talking_about_a_tool_is_sent_back(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    client = FakeClient(
        [
            reply(calls=[call("find_jobs", company="Datadog")]),
            reply("First, I'll call score_job with the job IDs."),  # talk, no call
            reply(calls=[call("score_job", job_id="greenhouse-1")]),
            reply("greenhouse-1 Senior SRE fits best (67)."),
        ]
    )
    run = agent.run_agent("Which Datadog job fits me best?", tools, client=client)
    assert [s["tool"] for s in run.steps] == ["find_jobs", "score_job"]
    assert run.corrections == 1

def test_a_plain_tool_mention_is_accepted(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    client = FakeClient(
        [
            reply(calls=[call("find_jobs", company="Acme")]),
            reply(
                "Acme isn't one of your companies. Call list_companies for the names."
            ),
        ]
    )
    run = agent.run_agent("Find roles at Acme", tools, client=client)
    assert run.corrections == 0 and run.warnings == []


def test_a_typed_tool_call_is_sent_back(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    client = FakeClient(
        [
            reply(calls=[call("list_companies")]),
            reply('find_jobs(["Datadog"])'),  # a call typed as text, not a call
            reply("I can search one company: Datadog."),
        ]
    )
    run = agent.run_agent("Which companies can you search?", tools, client=client)
    assert run.corrections == 1
    assert run.answer == "I can search one company: Datadog."


def test_list_shortlist_reads_saved_jobs(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    ask = [reply(calls=[call("list_shortlist")]), reply("Done.")]
    # No shortlist.json in tmp_path yet: an empty list, not an error
    client = FakeClient(ask)
    agent.run_agent("What have I saved?", tools, client=client)
    assert json.loads(client.tool_results[0]) == []
    # Now a shortlist with one job in it
    saved = [{**JOB, "id": "greenhouse-5", "reason": "Good fit"}]
    (tmp_path / "shortlist.json").write_text(json.dumps(saved))
    client = FakeClient(ask)
    agent.run_agent("What have I saved?", tools, client=client)
    assert [job["id"] for job in json.loads(client.tool_results[0])] == ["greenhouse-5"]


def test_saved_job_id_is_not_flagged(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    saved = [{**JOB, "id": "greenhouse-5", "reason": "Good fit"}]
    (tmp_path / "shortlist.json").write_text(json.dumps(saved))
    client = FakeClient(
        [
            reply(calls=[call("list_shortlist")]),
            reply("You already saved greenhouse-5."),
        ]
    )
    run = agent.run_agent("What have I saved?", tools, client=client)
    assert run.warnings == []  # the ID came from list_shortlist, so it's real
    assert "greenhouse-5" not in tools.jobs  # but read_job and score_job can't use it


def test_a_bare_tool_name_is_sent_back(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    client = FakeClient(
        [
            reply(calls=[call("list_companies")]),
            reply("find_jobs"),  # only a tool's name: not an answer, not a call
            reply("I can search one company: Datadog."),
        ]
    )
    run = agent.run_agent("Which companies can you search?", tools, client=client)
    assert run.corrections == 1
    assert run.answer == "I can search one company: Datadog."


def test_list_companies_gives_names_and_a_next_step(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    client = FakeClient([reply(calls=[call("list_companies")]), reply("Datadog.")])
    agent.run_agent("Which companies can you search?", tools, client=client)
    result = json.loads(client.tool_results[0])
    assert result["companies"] == ["Datadog"]
    assert "Answer the person with these names" in result["next"]


def test_a_far_away_made_up_score_is_sent_back(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    client = FakeClient(
        [
            reply(calls=[call("find_jobs", company="Datadog")]),
            # made up: the number is far from "score", and score_job never ran
            reply("The score for Senior SRE (greenhouse-1) is 92."),
            reply(calls=[call("score_job", job_id="greenhouse-1")]),
            reply("greenhouse-1 Senior SRE, Score: 67"),
        ]
    )
    run = agent.run_agent("Score the best Datadog job", tools, client=client)
    assert run.corrections == 1
    assert run.answer.endswith("Score: 67") and run.warnings == []


def test_a_job_id_is_not_a_score(monkeypatch, tmp_path):
    tools = make_tools(monkeypatch, tmp_path)
    client = FakeClient(
        [
            reply(calls=[call("find_jobs", company="Datadog")]),
            reply("I haven't scored greenhouse-1 yet."),  # the digits are the ID's
        ]
    )
    run = agent.run_agent("Find Datadog jobs", tools, client=client)
    assert run.corrections == 0 and run.warnings == []
