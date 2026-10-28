# links.py - turn a job link into the job's text, through public job-board APIs only
import re

from boards import fetch_ashby_job, fetch_greenhouse_job, fetch_lever_job

# boards.greenhouse.io/<slug>/jobs/<number> or job-boards.greenhouse.io/<slug>/jobs/<number>
# (?:job-)? means "job- may or may not be there"; (?P<slug>...) names the captured part
GREENHOUSE = re.compile(
    r"https?://(?:job-)?boards\.greenhouse\.io/(?P<slug>[\w-]+)/jobs/(?P<id>\d+)"
)
# An "embed" link: job-boards.greenhouse.io/embed/job_app?for=<slug>&token=<number>
GREENHOUSE_EMBED = re.compile(
    r"https?://(?:job-)?boards\.greenhouse\.io/embed/job_app"
    r"\?for=(?P<slug>[\w-]+)&token=(?P<id>\d+)"
)
# jobs.lever.co/<slug>/<id>, where the ID looks like 8f2c1a3e-1b2c-4d5e-9f00-1234567890ab
LEVER = re.compile(r"https?://jobs\.lever\.co/(?P<slug>[\w.-]+)/(?P<id>[0-9a-f-]{36})")
# jobs.ashbyhq.com/<slug>/<id>, the same kind of 36-character ID as Lever;
# a link ending in /application (the apply page) still matches
ASHBY = re.compile(
    r"https?://jobs\.ashbyhq\.com/(?P<slug>[\w.%-]+)/(?P<id>[0-9a-f-]{36})"
)

PASTE_INSTEAD = (
    "HireOps can read job links from Greenhouse, Lever and Ashby boards only. For any "
    "other site (LinkedIn, Workday bank career sites and others), copy the job text "
    "from the page and paste it into the box below."
)


class UnsupportedLink(ValueError):
    """A link HireOps can't read through a public API; paste the job text instead."""


def parse_link(url):
    """Return (board, slug, job_id) for a Greenhouse, Lever or Ashby job link."""
    url = url.strip()
    for board, pattern in (
        ("greenhouse", GREENHOUSE),
        ("greenhouse", GREENHOUSE_EMBED),
        ("lever", LEVER),
        ("ashby", ASHBY),
    ):
        found = pattern.match(url)  # match() checks from the start of the text
        if found:
            return board, found.group("slug"), found.group("id")
    raise UnsupportedLink(PASTE_INSTEAD)


def job_from_link(url):
    """Read one job from its link: the standard job dictionary from boards.py."""
    board, slug, job_id = parse_link(url)
    if board == "greenhouse":
        return fetch_greenhouse_job(slug, job_id)
    if board == "ashby":
        return fetch_ashby_job(slug, job_id)
    return fetch_lever_job(slug, job_id)
