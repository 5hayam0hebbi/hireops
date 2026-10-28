# test_alerts.py - checks for reading job-alert emails (uses the fictional samples)
from alerts import job_from_link, read_alerts
from radar import title_fits

LINKEDIN_LINK = "https://www.linkedin.com/comm/jobs/view/4000000001/?trackingId=abc"


def test_linkedin_link_becomes_a_job():
    job = job_from_link(LINKEDIN_LINK, "Director, Site Reliability Engineering")
    assert job["id"] == "linkedin-4000000001"
    assert job["url"] == "https://www.linkedin.com/jobs/view/4000000001/"


def test_view_job_button_is_skipped():
    # A one-word link like "View" isn't a title, so it's skipped
    assert job_from_link(LINKEDIN_LINK, "View") is None


def test_other_links_are_skipped():
    assert job_from_link("https://www.linkedin.com/feed/", "See your feed now") is None


def test_sample_emails_give_each_job_once():
    jobs = read_alerts("samples/alerts")
    ids = [job["id"] for job in jobs]
    # job 4000000001 is in both sample emails, but it's kept only once
    assert ids.count("linkedin-4000000001") == 1
    assert len(jobs) == 4


def test_missing_folder_gives_no_jobs():
    assert read_alerts("no/such/folder") == []


def test_title_fits_skips_excluded_words():
    titles, exclude = ["SRE", "DevOps"], ["Junior"]
    assert title_fits({"title": "SRE Manager"}, titles, exclude)
    assert not title_fits({"title": "Junior DevOps Engineer"}, titles, exclude)