# evals/snapshot_jobs.py - save today's jobs for the eval companies to a file, once.
# The eval reads that file instead of the live boards, so every run sees the same jobs.
# Run from the repo folder: python evals/snapshot_jobs.py
import json
import sys

sys.path.insert(0, ".")  # lets this file in evals/ import radar.py from the repo folder
from radar import FETCHERS, load_json, title_fits

EVAL_COMPANIES = ["Cloudflare", "Datadog", "GitLab"]  # the companies in agent_cases.json


def main():
    config = load_json("radar_config.json")
    sample = {}
    for company in config["companies"]:
        if company["name"] in EVAL_COMPANIES:
            fetch = FETCHERS[company["board"]]
            found = fetch(company["name"], company["slug"])
            # Keep only titles find_jobs would show, and at most 10 per company
            fits = [j for j in found if title_fits(j, config["titles"], config["exclude"])]
            sample[company["name"]] = fits[:10]
    with open("evals/sample_jobs.json", "w") as f:
        json.dump(sample, f, indent=2)
    for name, jobs in sample.items():
        print(f"{name}: {len(jobs)} jobs")


if __name__ == "__main__":
    main()