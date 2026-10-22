# radar.py - HireOps tool 2 (Job Radar): new matching roles at your target companies
import json
import logging

import requests

from boards import fetch_greenhouse, fetch_lever
from matcher import mentions

logger = logging.getLogger(__name__)

# Which function reads which kind of board. A dictionary can hold functions too.
FETCHERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever}


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


def main():
    logging.basicConfig(
        filename="hireops.log",
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    config = load_json("radar_config.json")

    print("Reading job boards...")
    jobs = fetch_all(config["companies"])
    titles, places, exclude = config["titles"], config["locations"], config["exclude"]
    matches = [job for job in jobs if is_match(job, titles, places, exclude)]
    print(f"\n{len(matches)} of {len(jobs)} jobs match your titles and places:\n")
    for job in matches:
        print(f"{job['company']} | {job['title']}")
        print(f"   {job['location']}")
        print(f"   {job['url']}")
    logger.info("Job Radar: %s jobs read, %s match", len(jobs), len(matches))


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as error:
        print(f"Couldn't find the file {error.filename}. Check the name and try again.")