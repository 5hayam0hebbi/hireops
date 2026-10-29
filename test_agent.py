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
    assert "Call list_companies" in client.tool_results[0]


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