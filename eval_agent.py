# eval_agent.py - grade Job Scout on a fixed set of goals, with the REAL model.
# Unit tests (test_agent.py) prove the code's guardrails work. This eval measures the
# model: does it pick the right tools, avoid the wrong ones, and never invent a job?
# Run it after every change to the prompt, the tool descriptions or the model.
import json
import time
from datetime import date
from pathlib import Path

import agent
from radar import load_json


def never_approve(question):
    """During an eval nothing is saved: every save request gets an automatic no."""
    return False


def grade(case, run):
    """The reasons this run failed its case; an empty list means it passed.

    A must_call tool only counts if it WORKED: a call that came back with an error
    (like a made-up job ID) doesn't prove the model used the tool correctly.
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
        tools = agent.Tools(config, resume_text, skills, never_approve)
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