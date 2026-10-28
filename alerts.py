# alerts.py - read job-alert emails you saved as .eml files (LinkedIn and Indeed)
# Your own emails, read from files on your computer: no website is ever scraped.
import re
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path

# A LinkedIn job link looks like linkedin.com/comm/jobs/view/4012345678/?tracking...
# (?:comm/)? means "comm/ may or may not be there"; (\d+) captures the job's number
LINKEDIN = re.compile(r"linkedin\.com/(?:comm/)?jobs/view/(\d+)")
# An Indeed job link carries the job's ID after jk=, for example ...?jk=3f2a9c1e5b7d
INDEED = re.compile(r"indeed\.[a-z.]+/.*[?&]jk=([0-9a-f]+)")


class LinkCollector(HTMLParser):
    """Collects every link in an HTML email as (address, the words you click)."""

    def __init__(self):
        super().__init__()  # run HTMLParser's own setup first
        self.links = []  # finished links: (href, text)
        self.href = None  # the address of the link we're inside, if any
        self.words = []  # the words seen inside that link so far

    def handle_starttag(self, tag, attrs):
        # Called for every opening tag; attrs is a list like [("href", "https://...")]
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.words = []

    def handle_data(self, data):
        # Called for the text between tags; keep it only inside a link
        if self.href:
            self.words.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href:
            text = " ".join(" ".join(self.words).split())  # squeeze the spaces
            self.links.append((self.href, text))
            self.href = None


def email_links(path):
    """Every (address, text) link in a saved .eml email file."""
    with open(path, "rb") as f:  # "rb" = read the raw bytes
        message = BytesParser(policy=policy.default).parse(f)
    body = message.get_body(preferencelist=("html",))
    if body is None:  # a text-only email: no links with words to click
        return []
    collector = LinkCollector()
    collector.feed(body.get_content())  # feed() reads the HTML and fills .links
    return collector.links


def job_from_link(href, text):
    """Turn one email link into Job Radar's standard job shape, or None if it isn't a job."""
    found = LINKEDIN.search(href)
    if found:
        job_id = found.group(1)  # group(1) is the part captured by (\d+)
        source, url = "LinkedIn", f"https://www.linkedin.com/jobs/view/{job_id}/"
    else:
        found = INDEED.search(href)
        if not found:
            return None  # an unsubscribe, profile or logo link
        job_id = found.group(1)
        source, url = "Indeed", f"https://ca.indeed.com/viewjob?jk={job_id}"
    if len(text.split()) < 2:
        return None  # "View job" buttons and image links: the title is in another link
    return {
        "id": f"{source.lower()}-{job_id}",
        "company": f"{source} alert",
        "title": text,
        "location": "",
        "url": url,
        "description": "",
    }


def read_alerts(folder):
    """Every job in every .eml file in the folder, each job only once."""
    jobs = {}  # a dictionary keyed by ID, so the same job twice is kept once
    # sorted() reads the files in name order; glob("*.eml") finds the .eml files
    for path in sorted(Path(folder).glob("*.eml")):
        for href, text in email_links(path):
            job = job_from_link(href, text)
            if job and job["id"] not in jobs:
                jobs[job["id"]] = job
    return list(jobs.values())


if __name__ == "__main__":
    for job in read_alerts("samples/alerts"):
        print(f"{job['company']} | {job['title']}")
        print(f"   {job['url']}")