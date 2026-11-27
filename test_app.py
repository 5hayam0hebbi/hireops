# test_app.py - checks the web pages work, in a pretend browser (no AI, no internet)
from streamlit.testing.v1 import AppTest

import coach
import decoder
import radar
from decoder import Bullet, Decoded
from matcher import MatchResult

JOB = "Senior SRE. You will run Kubernetes on Azure with Terraform and Python."
WAIT = 30  # seconds a page may take to run; GitHub's computers can be slow


def test_home_page_loads():
    page = AppTest.from_file("app.py").run(timeout=WAIT)
    assert not page.exception  # the page ran without an error
    assert page.title[0].value == "HireOps"


def test_decode_with_rules_only():
    page = AppTest.from_file("pages/1_JD_Decoder.py").run(timeout=WAIT)
    page.text_area[0].input(JOB)  # type the job into the text box
    page.toggle[0].set_value(False)  # AI off: rules only
    page.button[0].click().run(timeout=WAIT)  # click Decode; the page runs again
    assert not page.exception
    shown = " ".join(item.value for item in page.markdown)
    assert "Kubernetes" in shown and "rules only" in shown

def test_linkedin_link_asks_you_to_paste():
    page = AppTest.from_file("pages/1_JD_Decoder.py").run(timeout=WAIT)
    page.text_input[0].input("https://www.linkedin.com/jobs/view/4000000001/")
    page.button[0].click().run(timeout=WAIT)
    assert "paste it into the box" in page.info[0].value



RESUME = b"""# Alex Rivera
Director, Site Reliability Engineering
- Led a team of 25 engineers running 24x7 operations
- Ran incident management for 300+ critical applications
"""
BULLET = "Led incident management for 300+ critical applications with a 24x7 team"


def fake_decode(job_text, resume_text="", use_ai=True, progress=None):
    """Stands in for decode(): one suggested bullet, no AI, no waiting."""
    found = Decoded(wanted=["Incident management"], used_ai=True)
    found.result = MatchResult(wanted=found.wanted, have=found.wanted)
    found.bullets = [
        Bullet(BULLET, [], source="Ran incident management for 300+ critical applications")
    ]
    return found


def test_add_a_bullet_and_download_a_copy(monkeypatch):
    monkeypatch.setattr(decoder, "decode", fake_decode)  # the page gets the fake
    page = AppTest.from_file("pages/1_JD_Decoder.py").run(timeout=WAIT)
    page.text_area[0].input(JOB)
    page.file_uploader[0].upload("resume.md", RESUME, "text/markdown")
    page.button[0].click().run(timeout=WAIT)
    page.checkbox[0].check().run(timeout=WAIT)  # tick Include on bullet 1
    page.text_area[1].input(BULLET + " in 2031").run(timeout=WAIT)  # edit it
    assert not page.exception
    assert "2031 is not in your resume" in [w.value for w in page.warning]
    assert page.selectbox[0].value == 0  # its source line's section is picked
    assert page.download_button[0].proto.label == "Download updated resume"
    shown = " ".join(c.value for c in page.caption)
    assert "resume-job.md" in shown  # no job name typed, so "job"


def test_coach_page_with_rules_only(monkeypatch, tmp_path):
    monkeypatch.setattr(coach, "BANK", tmp_path / "answers.json")  # not private/
    page = AppTest.from_file("pages/2_Interview_Coach.py").run(timeout=WAIT)
    page.text_area[0].input(JOB)
    page.toggle[0].set_value(False)  # AI off: template questions
    page.button[0].click().run(timeout=WAIT)  # Get likely questions
    assert not page.exception
    shown = " ".join(item.value for item in page.markdown)
    assert "Tell me about a time you used Kubernetes" in shown
    page.text_area[1].input("I led the bridge for 3 hours.").run(timeout=WAIT)
    assert page.button[1].disabled  # STAR feedback needs the AI
    page.button[2].click().run(timeout=WAIT)  # Save to my answer bank
    assert "Saved: 1 in your bank" in page.success[0].value


def test_coach_feedback_verdict(monkeypatch):
    def fake_feedback(question, answer):
        scores = {"Situation": 2, "Task": 2, "Action": 1, "Result": 0}
        return coach.Feedback(question, scores, "Add the result.", "I led it.", [])

    monkeypatch.setattr(coach, "star_feedback", fake_feedback)
    page = AppTest.from_file("pages/2_Interview_Coach.py").run(timeout=WAIT)
    page.text_area[0].input(JOB)
    page.toggle[0].set_value(False)
    page.button[0].click().run(timeout=WAIT)
    page.toggle[0].set_value(True)  # the AI on again, for the feedback button
    page.text_area[1].input("I led the bridge.").run(timeout=WAIT)
    page.button[1].click().run(timeout=WAIT)
    assert "Work on the Result part first." in page.info[-1].value


def fake_find(config, resume_text, skills, alerts="private/alerts", seen=()):
    """Stands in for find_roles(): one role, no job boards."""
    role = {
        "id": "a",
        "score": 75,
        "company": "Example Bank",
        "title": "Senior SRE",
        "location": "Toronto",
        "missing": ["Terraform"],
        "url": "https://example.com/a",
    }
    return [role], [], 12  # matches, alert jobs, jobs read


def test_radar_page(monkeypatch):
    monkeypatch.setattr(radar, "find_roles", fake_find)  # tests never read boards
    page = AppTest.from_file("pages/3_Job_Radar.py").run(timeout=WAIT)
    page.file_uploader[0].upload("resume.md", RESUME, "text/markdown")
    page.button[0].click().run(timeout=WAIT)  # Check the job boards now
    assert not page.exception
    assert "Read 12 open jobs" in " ".join(m.value for m in page.markdown)
    assert page.dataframe[0].value.iloc[0]["Company"] == "Example Bank"


def test_radar_minimum_match(monkeypatch):
    monkeypatch.setattr(radar, "find_roles", fake_find)
    page = AppTest.from_file("pages/3_Job_Radar.py").run(timeout=WAIT)
    page.file_uploader[0].upload("resume.md", RESUME, "text/markdown")
    page.button[0].click().run(timeout=WAIT)
    page.slider[0].set_value(80).run(timeout=WAIT)  # the role is 75%
    assert page.dataframe[0].value.empty