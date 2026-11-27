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


def test_feedback_flags_invented_numbers(monkeypatch):
    scores = coach.StarScores(
        situation=2,
        task=1,
        action=2,
        result=1,
        tip="Say what changed.",
        tighter="I led the bridge and cut the outage to 20 minutes.",
    )
    monkeypatch.setattr(coach, "ask", fake_answer(scores))
    found = coach.star_feedback("Tell me about an outage.", "I led the bridge.")
    assert found.total() == 6
    assert found.invented == ["20"]  # the answer never said 20


def test_answer_notes():
    assert coach.answer_notes("I led the bridge.")[0].startswith("4 words")
    long_answer = " ".join(["word"] * 400) + " 30"
    assert coach.answer_notes(long_answer) == [
        "401 words: aim for under 2 minutes (about 300 words)."
    ]


def test_answer_bank(tmp_path):
    bank = tmp_path / "answers.json"  # tmp_path = a fresh folder just for this test
    assert coach.load_bank(bank) == []
    assert coach.save_answer("Q1?", "My answer", bank) == 1
    assert coach.save_answer("Q2?", "Another", bank) == 2
    assert coach.load_bank(bank)[1]["question"] == "Q2?"