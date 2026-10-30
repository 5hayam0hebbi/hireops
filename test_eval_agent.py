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


def ran(*steps):
    """A finished run with these (tool, result) steps, numbered from 1."""
    return agent.Run(
        answer="Done.",
        steps=[
            {"step": number, "tool": tool, "result": result}
            for number, (tool, result) in enumerate(steps, start=1)
        ],
    )


ORDER = {**CASE, "must_call_in_order": ["find_jobs", "score_job"]}
GUESS = "Error: Unknown job ID 'greenhouse-1'. Use an ID that find_jobs returned."


def test_tools_in_the_right_order_pass():
    run = ran(("find_jobs", "jobs found"), ("score_job", "score 80"))
    assert eval_agent.grade(ORDER, run) == []


def test_tools_out_of_order_fail():
    run = ran(("score_job", "score 80"), ("find_jobs", "jobs found"))
    assert eval_agent.grade(ORDER, run) == [
        "tools ran out of order: find_jobs before score_job"
    ]


def test_a_guess_that_recovered_still_fails():
    # The failed score_job doesn't count for order, so order passes,
    # but the guessed ID still fails the run
    run = ran(("score_job", GUESS), ("find_jobs", "jobs found"), ("score_job", "80"))
    assert eval_agent.grade(ORDER, run) == ["score_job tried a job ID no tool returned"]


def test_a_guessed_job_id_fails():
    run = ran(("find_jobs", "jobs found"), ("save_job", GUESS))
    assert eval_agent.grade(CASE, run) == ["save_job tried a job ID no tool returned"]


def test_other_errors_dont_count_as_guesses():
    # Like the Acme Rockets case: telling the person a company isn't listed is right
    run = ran(("find_jobs", "Error: No company called 'Acme Rockets'."))
    assert eval_agent.grade(CASE, run) == []
