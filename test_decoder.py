# test_decoder.py - checks for decoder.py, with a FAKE AI (tests never call Ollama)
import decoder
from extract import JobInsights, Requirement

JOB = "We need Python, Kubernetes and Terraform. Strong incident management."
RESUME = "- Wrote Python automation\n- Ran incident management for 300 apps"


def fake_insights(job_text):
    """Stands in for extract(): always 'finds' the same three skills."""
    return JobInsights(
        role_title="SRE",
        seniority="senior",
        requirements=[
            Requirement(name="Python", importance="must-have"),
            Requirement(name="Kubernetes", importance="must-have"),
            Requirement(name="Terraform", importance="nice-to-have"),
        ],
        red_flags=[],
    )


def no_ollama(*args):
    """Stands in for any AI function when Ollama isn't running."""
    raise ConnectionError("Ollama isn't running")


def test_rules_only_uses_skills_json():
    decoded = decoder.decode(JOB, RESUME, use_ai=False)
    assert not decoded.used_ai
    assert "Python" in decoded.wanted
    assert decoded.result.have == ["Python", "Incident management"]


def test_no_resume_means_no_score():
    decoded = decoder.decode(JOB, "   ", use_ai=False)
    assert decoded.result is None
    assert decoded.best_score() == 0


def test_ai_off_falls_back_to_rules(monkeypatch):
    # monkeypatch swaps a function for this one test, then puts the real one back
    monkeypatch.setattr(decoder, "extract", no_ollama)
    decoded = decoder.decode(JOB, RESUME)
    assert not decoded.used_ai
    assert decoded.notes == ["Ollama isn't running, so this used rules only."]


def test_full_run_with_a_fake_ai(monkeypatch):
    monkeypatch.setattr(decoder, "extract", fake_insights)
    monkeypatch.setattr(
        decoder, "find_by_meaning", lambda missing, resume: {"Kubernetes": "Ran pods"}
    )
    monkeypatch.setattr(
        decoder,
        "suggest_bullets",
        lambda job, resume, focus: ["Automated 45 releases with Python across teams"],
    )
    messages = []  # the progress function below collects each message here
    decoded = decoder.decode(JOB, RESUME, progress=messages.append)
    assert decoded.used_ai
    assert decoded.result.score() == 33  # Python only: 1 of 3
    assert decoded.best_score() == 67  # plus Kubernetes, if that match is right
    assert decoded.bullets[0].invented == ["45"]  # 45 isn't in the resume
    assert len(messages) == 3