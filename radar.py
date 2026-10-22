# radar.py - HireOps tool 2 (Job Radar): new matching roles at your target companies
import argparse
import json
import logging

import requests

from boards import fetch_greenhouse, fetch_lever
from matcher import match, mentions

logger = logging.getLogger(__name__)

# Which function reads which kind of board. A dictionary can hold functions too.
FETCHERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever}
SEEN_FILE = "seen.json"


def load_json(path):
    """Read a JSON file."""
    with open(path) as f:
        return json.load(f)


def fetch_all(companies):
    """Every open job at every company. A board that fails is skipped, not fatal."""
    jobs = []
    for company in companies:
        # Pick the right function for this company's board
        fetch = FETCHERS[company["board"]]
        try:
            found = fetch(company["name"], company["slug"])
            print(f"  {company['name']}: {len(found)} open jobs")
            # .extend adds every item of found to the end of jobs
            jobs.extend(found)
        except requests.RequestException as error:
            print(f"  {company['name']}: skipped ({error})")
            logger.warning("Could not read %s: %s", company["name"], error)
    return jobs


def is_match(job, titles, locations, exclude):
    """True if the title and location fit, and the title has no excluded word."""
    # any() is True if at least one of the checks inside it is True
    title_ok = any(mentions(job["title"], word) for word in titles)
    location_ok = any(mentions(job["location"], place) for place in locations)
    excluded = any(mentions(job["title"], word) for word in exclude)
    return title_ok and location_ok and not excluded


def load_seen(path=SEEN_FILE):
    """IDs of jobs already reported. An empty set on the very first run."""
    try:
        return set(load_json(path))
    # No file yet, or an empty or broken file: start fresh instead of crashing
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen(seen, path=SEEN_FILE):
    """Remember the reported IDs. JSON can't store a set, so save a sorted list."""
    with open(path, "w") as f:
        json.dump(sorted(seen), f, indent=2)


def new_only(jobs, seen):
    """The jobs whose ID isn't in seen yet."""
    return [job for job in jobs if job["id"] not in seen]


def by_score(job):
    """Used by sorted(): sort jobs by their score."""
    return job["score"]


def score_jobs(jobs, resume_text, skills):
    """Give each job JD Decoder's match score, then put the best match first."""
    for job in jobs:
        result = match(job["description"], resume_text, skills)
        # Add two new keys to this job's dictionary
        job["score"] = result.score()
        job["missing"] = result.missing()
    # key=by_score sorts by each job's score; reverse=True puts the highest first
    return sorted(jobs, key=by_score, reverse=True)


def main():
    parser = argparse.ArgumentParser(description="New roles at your target companies.")
    parser.add_argument("-r", "--resume", default="samples/resume.md", help="resume")
    parser.add_argument("--all", action="store_true", help="include roles seen before")
    args = parser.parse_args()

    logging.basicConfig(
        filename="hireops.log",
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    config = load_json("radar_config.json")
    skills = load_json("skills.json")
    with open(args.resume) as f:
        resume_text = f.read()

    print("Reading job boards...")
    jobs = fetch_all(config["companies"])
    titles, places, exclude = config["titles"], config["locations"], config["exclude"]
    matches = [job for job in jobs if is_match(job, titles, places, exclude)]

    seen = load_seen()
    if not args.all:
        matches = new_only(matches, seen)
    if not matches:
        print("\nNo new matching roles since the last run.")

    matches = score_jobs(matches, resume_text, skills)
    for job in matches:
        # :>3 makes every score 3 characters wide, so the scores line up
        print(f"\n{job['score']:>3}% | {job['company']} | {job['title']}")
        print(f"       {job['location']}")
        print(f"       {job['url']}")

    # Remember everything reported today, so tomorrow shows only new roles
    seen.update(job["id"] for job in matches)
    save_seen(seen)
    logger.info("Job Radar: %s jobs read, %s new matches", len(jobs), len(matches))


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as error:
        print(f"Couldn't find the file {error.filename}. Check the name and try again.")