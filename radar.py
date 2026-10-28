# radar.py - HireOps tool 2 (Job Radar): new matching roles at your target companies
import argparse
import json
import logging
import time
from pathlib import Path

import requests

from alerts import read_alerts
from boards import fetch_ashby, fetch_greenhouse, fetch_lever
from matcher import match, mentions

logger = logging.getLogger(__name__)

# Which function reads which kind of board. A dictionary can hold functions too.
FETCHERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby}
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


def title_fits(job, titles, exclude):
    """True if the title has one of your titles and none of your excluded words."""
    # any() is True if at least one of the checks inside it is True
    title_ok = any(mentions(job["title"], word) for word in titles)
    excluded = any(mentions(job["title"], word) for word in exclude)
    return title_ok and not excluded


def is_match(job, titles, locations, exclude):
    """True if the title fits (see title_fits) and the location is one of yours."""
    location_ok = any(mentions(job["location"], place) for place in locations)
    return title_fits(job, titles, exclude) and location_ok


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
    """Used by sorted(): by score, then by how many skills matched."""
    # A tuple compares its first items, then the second ones if the first are equal,
    # so 100% with 6 of 6 skills comes before 100% with 1 of 1
    return (job["score"], len(job["have"]))


def score_jobs(jobs, resume_text, skills):
    """Give each job JD Decoder's match score, then put the best match first."""
    for job in jobs:
        result = match(job["description"], resume_text, skills)
        # Add two new keys to this job's dictionary
        job["score"] = result.score()
        job["have"] = result.have
        job["wanted"] = result.wanted
        job["missing"] = result.missing()
    # key=by_score sorts by each job's score; reverse=True puts the highest first
    return sorted(jobs, key=by_score, reverse=True)


def write_digest(jobs, alert_jobs=(), folder="digests"):
    """Save the results as a Markdown table, for example digests/2026-10-23.md."""
    # Today's date as text: %Y is the year, %m the month, %d the day
    today = time.strftime("%Y-%m-%d")
    # Make the folder; exist_ok=True means no complaint if it's already there
    Path(folder).mkdir(exist_ok=True)
    # The / joins the folder and the file name into one path
    path = Path(folder) / f"{today}.md"
    lines = [
        f"# Job Radar - {today}",
        "",
        f"{len(jobs)} new matching roles, best match first.",
        "",
        "| Match | Company | Role | Location |",
        "|---|---|---|---|",
    ]
    for job in jobs:
        # A Markdown link looks like [text](address)
        link = f"[{job['title']}]({job['url']})"
        row = f"| {job['score']}% | {job['company']} | {link} | {job['location']} |"
        lines.append(row)
        if alert_jobs:  # an empty list or () counts as False, so this part is skipped
            lines += ["", "## From your job alerts", "", "| Source | Role |", "|---|---|"]
            for job in alert_jobs:
                lines.append(f"| {job['company']} | [{job['title']}]({job['url']}) |")
    # Join the lines with line breaks and write them all to the file
    path.write_text("\n".join(lines) + "\n")
    return path


def main():
    parser = argparse.ArgumentParser(description="New roles at your target companies.")
    parser.add_argument("-r", "--resume", default="samples/resume.md", help="resume")
    parser.add_argument("--all", action="store_true", help="include roles seen before")
    parser.add_argument(
        "--alerts", default="private/alerts", help="folder of saved alert emails"
    )
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
    # Jobs from your saved alert emails have no place or job text: check the title only
    alert_jobs = [j for j in read_alerts(args.alerts) if title_fits(j, titles, exclude)]

    seen = load_seen()
    if not args.all:
        matches = new_only(matches, seen)
        alert_jobs = new_only(alert_jobs, seen)
    if not matches and not alert_jobs:
        print("\nNo new matching roles since the last run.")

    matches = score_jobs(matches, resume_text, skills)
    for job in matches:
        # :>3 makes every score 3 characters wide, so the scores line up
        found = f"{len(job['have'])} of {len(job['wanted'])} skills"
        print(f"\n{job['score']:>3}% ({found}) | {job['company']} | {job['title']}")
        print(f"       {job['location']}")
        print(f"       {job['url']}")
        if job["missing"]:
            # [:3] keeps the first three; join glues them together with commas
            print(f"       Missing: {', '.join(job['missing'][:3])}")

        if alert_jobs:
            print(f"\nFrom your job alerts ({len(alert_jobs)}; open each one to read it):")
        for job in alert_jobs:
            print(f"  {job['company']} | {job['title']}")
            print(f"       {job['url']}")

    if matches or alert_jobs:
        path = write_digest(matches, alert_jobs)
        print(f"\nSaved {path}")

    # Remember everything reported today, so tomorrow shows only new roles
    seen.update(job["id"] for job in matches + alert_jobs)

    # Remember everything reported today, so tomorrow shows only new roles
    seen.update(job["id"] for job in matches)
    save_seen(seen)
    logger.info("Job Radar: %s jobs read, %s new matches", len(jobs), len(matches))


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as error:
        print(f"Couldn't find the file {error.filename}. Check the name and try again.")
