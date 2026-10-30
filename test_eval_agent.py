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


import json as _json

SAVE_TOP_CASE = {**CASE, "must_save_top_score": True}


def scored_run(scored, saved_id):
    """A run where score_job was called for each (id, score) pair, then save_job saved saved_id."""
    steps = []
    for i, (job_id, score) in enumerate(scored, start=1):
        steps.append({
            "step": i,
            "tool": "score_job",
            "args": {"job_id": job_id},
            "result": _json.dumps({"id": job_id, "score": score, "have": [], "missing": []}),
        })
    steps.append({
        "step": len(scored) + 1,
        "tool": "save_job",
        "args": {"job_id": saved_id},
        "result": '{"saved": false, "note": "The person said no."}',
    })
    return agent.Run(answer="Done.", steps=steps)


def test_must_save_top_score_passes_when_best_is_saved():
    run = scored_run([("greenhouse-1", 80), ("greenhouse-2", 50)], "greenhouse-1")
    assert eval_agent.grade(SAVE_TOP_CASE, run) == []


def test_must_save_top_score_fails_when_lower_scored_job_is_saved():
    run = scored_run([("greenhouse-1", 80), ("greenhouse-2", 50)], "greenhouse-2")
    problems = eval_agent.grade(SAVE_TOP_CASE, run)
    assert problems == [
        "saved greenhouse-2 (score 50) but greenhouse-1 had a higher score of 80"
    ]


def test_must_save_top_score_skipped_when_no_scores():
    # If the model never successfully scored a job, this check is silent (must_call
    # already catches the missing score_job call)
    run = ran(("save_job", '{"saved": false}'))
    assert eval_agent.grade(SAVE_TOP_CASE, run) == []


def test_must_save_top_score_reads_a_result_cut_at_200_characters():
    # A real score_job result lists the skills it found, so it runs past the
    # 200-character cut in run.steps and is no longer complete JSON
    long_result = _json.dumps(
        {"id": "greenhouse-1", "score": 80, "have": ["Kubernetes"] * 30, "missing": []}
    )[:200]
    run = scored_run([("greenhouse-2", 50)], "greenhouse-2")
    run.steps.insert(
        0,
        {"step": 0, "tool": "score_job", "args": {"job_id": "greenhouse-1"},
         "result": long_result},
    )
    problems = eval_agent.grade(SAVE_TOP_CASE, run)
    assert problems == [
        "saved greenhouse-2 (score 50) but greenhouse-1 had a higher score of 80"
    ]

def test_the_eval_never_reads_the_live_boards():
    tools = eval_agent.make_tools({"companies": []}, "resume", [])
    assert tools.fetch_jobs is not None  # a sample board, not FETCHERS
    assert tools.fetch_jobs("Cloudflare") == load_json(eval_agent.SAMPLE_JOBS)["Cloudflare"]


def test_sample_jobs_have_enough_to_compare():
    sample = load_json(eval_agent.SAMPLE_JOBS)
    for company in ["Cloudflare", "Datadog", "GitLab"]:
        assert len(sample[company]) >= 2  # the top-score check needs two to compare
        for job in sample[company]:
            assert {"id", "title", "location", "description"} <= job.keys()