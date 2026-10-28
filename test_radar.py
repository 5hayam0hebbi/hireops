# test_radar.py - checks for Job Radar that never touch the internet
from boards import clean, from_ashby, from_greenhouse, from_lever
from radar import is_match, new_only, score_jobs

# A made-up Greenhouse job, in the same shape the real API sends
GREENHOUSE_JOB = {
    "id": 123,
    "title": "Senior Site Reliability Engineer",
    "location": {"name": "Toronto, Canada"},
    "absolute_url": "https://example.com/jobs/123",
    "content": "&lt;p&gt;Run &lt;strong&gt;Kubernetes&lt;/strong&gt; on Azure.&lt;/p&gt;",
}

TITLES = ["SRE", "Site Reliability", "Platform"]
LOCATIONS = ["Toronto", "Remote"]


def job(title, location="Toronto", job_id="x"):
    """A small job dictionary for tests."""
    return {"id": job_id, "title": title, "location": location}


def test_clean_removes_html():
    assert clean("<p>Run <b>Kubernetes</b></p>") == "Run Kubernetes"


def test_from_greenhouse():
    result = from_greenhouse("Example Bank", GREENHOUSE_JOB)
    assert result["id"] == "greenhouse-123"
    assert result["location"] == "Toronto, Canada"
    assert result["description"] == "Run Kubernetes on Azure."


def test_title_and_location_match():
    assert is_match(job("Platform Engineer"), TITLES, LOCATIONS, [])


def test_wrong_title_does_not_match():
    assert not is_match(job("Account Executive"), TITLES, LOCATIONS, [])


def test_wrong_location_does_not_match():
    assert not is_match(job("SRE", location="Berlin, Germany"), TITLES, LOCATIONS, [])


def test_new_only_skips_seen_jobs():
    jobs = [job("SRE", job_id="a"), job("SRE", job_id="b")]
    assert new_only(jobs, {"a"}) == [jobs[1]]


def test_best_match_first():
    jobs = [
        # The resume covers 1 of this job's 2 skills: 50%
        {"id": "1", "description": "Python and Azure"},
        # The resume covers 1 of this job's 1 skill: 100%
        {"id": "2", "description": "Python only"},
    ]
    ranked = score_jobs(jobs, "I write Python", ["Python", "Azure"])
    assert [j["id"] for j in ranked] == ["2", "1"]
    assert ranked[0]["score"] == 100


LEVER_JOB = {
    "id": "abc",
    "text": "Platform Engineer",
    "categories": {"location": "Remote"},
    "hostedUrl": "https://example.com/abc",
    "descriptionPlain": "Python and Docker",
}


def test_from_lever():
    result = from_lever("Example Fintech", LEVER_JOB)
    assert result["id"] == "lever-abc"
    assert result["title"] == "Platform Engineer"
    assert result["description"] == "Python and Docker"


def test_excluded_word_blocks_a_match():
    assert not is_match(job("Junior Platform Engineer"), TITLES, LOCATIONS, ["Junior"])


def test_from_ashby_joins_all_places():
    ashby_job = {
        "id": "abc",
        "title": "Manager, Site Reliability Engineering",
        "location": "Toronto",
        "secondaryLocations": [{"location": "Montreal"}],
        "address": {"postalAddress": {"addressCountry": "Canada"}},
        "isRemote": True,
        "jobUrl": "https://example.com/abc",
        "descriptionHtml": "<p>Run <b>Kubernetes</b></p>",
    }
    result = from_ashby("Lightspeed", ashby_job)
    assert result["id"] == "ashby-abc"
    assert result["location"] == "Toronto; Montreal; Canada; Remote"
    assert result["description"] == "Run Kubernetes"
