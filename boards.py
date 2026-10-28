# boards.py - read job postings from public job-board APIs (no login, no key needed)
import html
import re

import requests

TIMEOUT = 20  # seconds to wait for a job board before giving up


def clean(text):
    """Turn a job board's HTML description into plain text."""
    # Greenhouse sends &lt;p&gt; instead of <p>; unescape turns it back into <p>
    text = html.unescape(text or "")
    # Replace every tag, like <p> or <li>, with a space
    text = re.sub(r"<[^>]+>", " ", text)
    # Squeeze runs of spaces and line breaks into one space
    return re.sub(r"\s+", " ", text).strip()


def from_greenhouse(company, job):
    """Turn one Greenhouse job into Job Radar's standard shape: a plain dictionary."""
    return {
        "id": f"greenhouse-{job['id']}",
        "company": company,
        "title": job["title"],
        "location": job["location"]["name"],
        "url": job["absolute_url"],
        "description": clean(job.get("content")),
    }


def fetch_greenhouse(company, slug):
    """Every open job on a company's Greenhouse board."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    # params adds ?content=true to the address, which asks for the full descriptions
    response = requests.get(url, params={"content": "true"}, timeout=TIMEOUT)
    # Turn an error answer from the board (like "404 Not Found") into a Python error
    response.raise_for_status()
    return [from_greenhouse(company, job) for job in response.json()["jobs"]]


def from_lever(company, job):
    """Turn one Lever job into the same standard shape."""
    return {
        "id": f"lever-{job['id']}",
        "company": company,
        "title": job["text"],
        # .get(key, "") gives "" if this job has no location
        "location": job["categories"].get("location", ""),
        "url": job["hostedUrl"],
        "description": clean(job.get("descriptionPlain")),
    }


def fetch_lever(company, slug):
    """Every open job on a company's Lever board."""
    url = f"https://api.lever.co/v0/postings/{slug}"
    response = requests.get(url, params={"mode": "json"}, timeout=TIMEOUT)
    response.raise_for_status()
    # Lever's answer is the list of jobs itself, so no ["jobs"] here
    return [from_lever(company, job) for job in response.json()]


def from_ashby(company, job):
    """Turn one Ashby job into the same standard shape."""
    # Ashby gives a main place, extra places, a country and a remote flag separately.
    # Join them into one text, so the place filter can find "Toronto" or "Canada".
    places = [job.get("location", "")]
    # "or []" covers a job with no extra places (None), so the loop still works
    places += [
        extra.get("location", "") for extra in job.get("secondaryLocations") or []
    ]
    postal = (job.get("address") or {}).get("postalAddress") or {}
    places.append(postal.get("addressCountry", ""))
    if job.get("isRemote"):
        places.append("Remote")
    return {
        "id": f"ashby-{job['id']}",
        "company": company,
        "title": job["title"],
        # Skip empty pieces, then join the rest with "; "
        "location": "; ".join(place for place in places if place),
        "url": job.get("jobUrl", ""),
        "description": clean(job.get("descriptionHtml") or job.get("descriptionPlain")),
    }


def fetch_ashby(company, slug):
    """Every open, listed job on a company's Ashby board."""
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    jobs = response.json()["jobs"]
    # isListed False means a hidden posting; .get(..., True) keeps jobs without the flag
    return [from_ashby(company, job) for job in jobs if job.get("isListed", True)]


if __name__ == "__main__":
    jobs = fetch_greenhouse("Cloudflare", "cloudflare")
    print(f"{len(jobs)} open jobs at Cloudflare. The first five:")
    for job in jobs[:5]:  # [:5] means "the first five items"
        print(f"  {job['title']} | {job['location']}")
