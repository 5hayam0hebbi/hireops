# test_eval_agent.py - tests for the eval runner. None of them call the AI or a job
# board: they only check how eval_agent.py sets up each case.
import agent
import eval_agent
from radar import load_json

# The shape of an eval case; each test adds the fields it needs
CASE = {"goal": "Which companies can you search?", "must_call": [], "must_not_call": []}


def finished(answer):
    """A finished run that gave this answer, with no tool calls and no warnings."""
    return agent.Run(answer=answer)


def test_every_case_uses_the_sample_shortlist():
    tools = eval_agent.make_tools({"companies": []}, "resume", [])
    assert tools.shortlist_file == eval_agent.SAMPLE_SHORTLIST
    assert tools.shortlist_file != "shortlist.json"  # never the real, private one


def test_sample_shortlist_has_what_list_shortlist_needs():
    saved = load_json(eval_agent.SAMPLE_SHORTLIST)
    assert saved  # at least one job, so the shortlist case has something to find
    for job in saved:
        assert {"id", "company", "title"} <= job.keys()  # <= means "all of these"


def test_answer_must_include_passes_when_named():
    case = {**CASE, "answer_must_include": ["Datadog", "GitLab"]}
    # Upper/lower case doesn't matter
    assert eval_agent.grade(case, finished("I can search datadog and GitLab.")) == []


def test_answer_must_include_fails_when_missing():
    case = {**CASE, "answer_must_include": ["Datadog", "GitLab"]}
    problems = eval_agent.grade(case, finished("find_jobs"))
    assert problems == [
        "answer doesn't mention Datadog",
        "answer doesn't mention GitLab",
    ]


def test_a_case_without_answer_must_include_skips_it():
    assert eval_agent.grade(CASE, finished("Anything at all.")) == []
