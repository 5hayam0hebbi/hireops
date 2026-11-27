# test_coach.py - checks for coach.py, with a FAKE AI (tests never call Ollama)
import coach
import decoder
from extract import JobInsights, Requirement

JOB = "Senior SRE. Lead incident management, run Kubernetes and automate with Python."
SKILLS = ["Incident management", "Kubernetes", "Python"]


def fake_answer(answer):
    """A fake ask(): whatever question it gets, it returns this answer."""
    return lambda prompt, shape, temperature=0: answer


def test_ai_questions_are_checked(monkeypatch):
    ideas = coach.Questions(
        questions=[
            coach.Question(
                text="Tell me about a time you led a major incident.",
                kind="behavioural",
                skill="Incident management",
            ),
            # Same question again: dropped
            coach.Question(
                text="Tell me about a time you led a major incident.",
                kind="behavioural",
                skill="Incident management",
            ),
            # A skill the job never mentions: dropped
            coach.Question(
                text="How do you tune Oracle databases?",
                kind="technical",
                skill="Oracle",
            ),
            # Not a question: dropped
            coach.Question(text="Kubernetes", kind="technical", skill="Kubernetes"),
        ]
    )
    monkeypatch.setattr(coach, "ask", fake_answer(ideas))
    found = coach.likely_questions(JOB, SKILLS)
    assert [q.text for q in found] == ["Tell me about a time you led a major incident."]


def test_template_questions_need_no_ai():
    found = coach.template_questions(SKILLS)
    assert len(found) == 3
    assert found[0].text.startswith("Tell me about a time you used Incident management")
    assert [q.kind for q in found] == ["behavioural", "behavioural", "technical"]
    

def test_questions_for_with_rules_only():
    found, notes = coach.questions_for(JOB, use_ai=False)  # skills.json, no AI
    assert found[0].text.startswith("Tell me about a time")
    assert notes == []


def test_questions_for_uses_the_must_haves(monkeypatch):
    def fake_extract(job_text):
        return JobInsights(
            role_title="SRE",
            seniority="senior",
            requirements=[
                Requirement(name="Kubernetes", importance="must-have"),
                Requirement(name="Python", importance="nice-to-have"),
            ],
            red_flags=[],
        )

    asked = []

    def fake_likely(job_text, skills):
        asked.append(skills)
        return []  # nothing passed the checks

    monkeypatch.setattr(decoder, "extract", fake_extract)
    monkeypatch.setattr(coach, "likely_questions", fake_likely)
    found, notes = coach.questions_for(JOB)
    assert asked == [["Kubernetes"]]  # only the must-have
    assert found[0].skill == "Kubernetes"  # template questions instead
    assert "templates instead" in notes[0]
