# test_links.py - checks for job links; the network is FAKED, so no website is called
import pytest

import boards
from links import UnsupportedLink, job_from_link, parse_link

LEVER_ID = "8f2c1a3e-1b2c-4d5e-9f00-1234567890ab"


def test_greenhouse_links():
    old = "https://boards.greenhouse.io/northwind/jobs/4012345"
    new = "https://job-boards.greenhouse.io/northwind/jobs/4012345?gh_src=x"
    assert parse_link(old) == ("greenhouse", "northwind", "4012345")
    assert parse_link(new) == ("greenhouse", "northwind", "4012345")


def test_lever_link():
    url = f"https://jobs.lever.co/contoso/{LEVER_ID}"
    assert parse_link(url) == ("lever", "contoso", LEVER_ID)


def test_other_sites_ask_you_to_paste():
    # pytest.raises checks that the code inside the with-block raises this error
    with pytest.raises(UnsupportedLink):
        parse_link("https://www.linkedin.com/jobs/view/4000000001/")


class FakeResponse:
    """Stands in for the answer requests.get() would give, without the internet."""

    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass  # a fake answer is never an error

    def json(self):
        return self.data


def test_lever_job_includes_its_lists(monkeypatch):
    posting = {
        "id": LEVER_ID,
        "text": "Platform Engineering Manager",
        "categories": {"location": "Toronto"},
        "hostedUrl": f"https://jobs.lever.co/contoso/{LEVER_ID}",
        "descriptionPlain": "Lead our platform team.",
        "lists": [{"text": "Requirements", "content": "<li>Kubernetes</li>"}],
    }
    # Swap requests.get inside boards.py for a fake that returns the posting above
    monkeypatch.setattr(
        boards.requests, "get", lambda url, timeout: FakeResponse(posting)
    )
    job = job_from_link(f"https://jobs.lever.co/contoso/{LEVER_ID}")
    assert job["title"] == "Platform Engineering Manager"
    assert job["description"] == "Lead our platform team. Requirements Kubernetes"


ASHBY_ID = "ca4434c0-9935-40aa-8bf9-5caaf0f2ce1b"


def test_ashby_links():
    url = f"https://jobs.ashbyhq.com/wealthsimple/{ASHBY_ID}"
    apply = f"https://jobs.ashbyhq.com/wealthsimple/{ASHBY_ID}/application"
    assert parse_link(url) == ("ashby", "wealthsimple", ASHBY_ID)
    assert parse_link(apply) == ("ashby", "wealthsimple", ASHBY_ID)


def test_ashby_job_picked_from_board(monkeypatch):
    board = {
        "jobs": [
            {"id": "other", "title": "Designer", "location": "Toronto"},
            {
                "id": ASHBY_ID,
                "title": "Senior SRE",
                "location": "Toronto",
                "isRemote": True,
                "jobUrl": f"https://jobs.ashbyhq.com/wealthsimple/{ASHBY_ID}",
                "descriptionHtml": "<p>Run our platform.</p>",
            },
        ]
    }
    monkeypatch.setattr(
        boards.requests, "get", lambda url, timeout: FakeResponse(board)
    )
    job = job_from_link(f"https://jobs.ashbyhq.com/wealthsimple/{ASHBY_ID}")
    assert job["title"] == "Senior SRE"
    assert job["location"] == "Toronto; Remote"
    assert job["description"] == "Run our platform."


def test_ashby_closed_job(monkeypatch):
    monkeypatch.setattr(
        boards.requests, "get", lambda url, timeout: FakeResponse({"jobs": []})
    )
    with pytest.raises(LookupError):
        job_from_link(f"https://jobs.ashbyhq.com/wealthsimple/{ASHBY_ID}")