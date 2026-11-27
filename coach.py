# coach.py - Interview Coach's engine: likely questions for a job, and STAR feedback
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ai import AIError, ask
from bullets import unsupported_numbers
from decoder import decode, say_nothing
from matcher import mentions

# Your saved answers: in private/, which .gitignore keeps out of GitHub
BANK = Path("private/answers.json")


# One interview question from the AI, and the job skill it tests
class Question(BaseModel):
    text: str = Field(max_length=300)
    # Literal[...] = only these exact words are allowed
    kind: Literal["behavioural", "technical"]
    skill: str = Field(max_length=80)


class Questions(BaseModel):
    questions: list[Question] = Field(max_length=10)  # a cap, so it can't go on forever


QUESTIONS_PROMPT = """You are an experienced hiring manager. Write 8 interview questions
you would ask for the job below: 5 behavioural questions that start with "Tell me about
a time" and 3 technical questions. Tie each question to ONE skill from this list and
copy that skill exactly into "skill".

Skills this job asks for: {skills}

Job description:
{job}"""


def is_question(text):
    """True if the text is a real question, not a heading or a statement."""
    starts = ("tell me", "describe", "walk me", "give me", "how ", "what ", "why ")
    return text.endswith("?") or text.lower().startswith(starts)


def likely_questions(job_text, skills):
    """Up to 8 questions from the AI. The code keeps only questions about a skill
    the posting really names, and drops repeats."""
    prompt = QUESTIONS_PROMPT.format(skills=", ".join(skills), job=job_text)
    found = ask(prompt, Questions, temperature=0.3).questions
    kept, seen = [], set()
    for question in found:
        text = question.text.strip()
        if not is_question(text):
            continue  # not a question
        if not mentions(job_text, question.skill):
            continue  # a skill the posting never mentions: the AI made it up
        if text.lower() in seen:
            continue  # the same question twice
        seen.add(text.lower())
        kept.append(question)
    return kept[:8]  # [:8] keeps at most the first 8


def template_questions(skills):
    """Rules-only questions (no AI): 5 behavioural, then 3 technical, from the skills."""
    questions = []
    if len(skills) < 6:  # too few for both kinds: the last one is technical
        behavioural, technical = skills[:-1], skills[-1:]
    else:
        behavioural, technical = skills[:5], skills[5:8]
    for skill in behavioural:
        text = f"Tell me about a time you used {skill} to solve a real problem."
        questions.append(Question(text=text, kind="behavioural", skill=skill))
    for skill in technical:
        text = f"How would you explain your approach to {skill} to a new teammate?"
        questions.append(Question(text=text, kind="technical", skill=skill))
    return questions


def questions_for(job_text, use_ai=True, progress=say_nothing):
    """Likely questions for a job, and notes for you. Never crashes if the AI is off.

    The job's skills come from decode() (JD Decoder's engine): the AI's list, or
    the backup list in skills.json when the AI is off or not running.
    """
    decoded = decode(job_text, use_ai=use_ai, progress=progress)
    notes = list(decoded.notes)  # for example "Ollama isn't running..."
    skills = decoded.wanted
    if decoded.insights and decoded.insights.must_haves:
        skills = decoded.insights.must_haves  # the must-haves matter most
    if not skills:
        notes.append("No skills found in this job, so there are no questions.")
        return [], notes
    if decoded.used_ai:
        progress("Writing likely questions...")
        try:
            found = likely_questions(job_text, skills)
            if found:
                return found, notes
            notes.append("The AI's questions didn't pass the checks: templates instead.")
        except (ConnectionError, AIError) as error:
            notes.append(f"No AI questions this time: {error}")
    return template_questions(skills), notes


# The AI's STAR scores: 0 = missing, 1 = vague, 2 = clear. ge/le = "at least/at most"
class StarScores(BaseModel):
    situation: int = Field(ge=0, le=2)
    task: int = Field(ge=0, le=2)
    action: int = Field(ge=0, le=2)
    result: int = Field(ge=0, le=2)
    tip: str = Field(max_length=300)
    tighter: str = Field(max_length=1500)


FEEDBACK_PROMPT = """You are an interview coach. Score the answer below on STAR,
0 to 2 for each part (0 = missing, 1 = vague, 2 = clear and specific):
situation = the context; task = what the person had to do; action = what THEY did
(not the team); result = what changed, ideally with a number.
tip = the one change that would help this answer most, in one sentence.
tighter = the same answer rewritten in under 150 words, in the first person.
Use ONLY facts from the answer. Never add numbers, tools or results it doesn't contain.

Question: {question}

Answer: {answer}"""


# What the page shows after "Get STAR feedback"
@dataclass
class Feedback:
    question: str
    scores: dict[str, int]  # {"Situation": 2, "Task": 1, ...}
    tip: str
    tighter: str
    invented: list[str]  # numbers in the tighter version that your answer never had

    def total(self):
        """All four scores added up, out of 8."""
        return sum(self.scores.values())


def star_feedback(question, answer):
    """The AI scores your answer; the code checks its rewrite for invented numbers."""
    prompt = FEEDBACK_PROMPT.format(question=question, answer=answer)
    found = ask(prompt, StarScores, temperature=0.2)
    scores = {
        "Situation": found.situation,
        "Task": found.task,
        "Action": found.action,
        "Result": found.result,
    }
    tighter = found.tighter.strip()
    invented = sorted(unsupported_numbers(tighter, answer))  # same check as bullets
    return Feedback(question, scores, found.tip.strip(), tighter, invented)


def answer_notes(answer):
    """Plain rules about length and numbers. They work with the AI off, too."""
    words = len(answer.split())
    notes = []
    if words < 60:
        notes.append(f"{words} words: a full STAR answer is usually 150 to 300.")
    elif words > 350:
        notes.append(f"{words} words: aim for under 2 minutes (about 300 words).")
    if not any(character.isdigit() for character in answer):
        notes.append("No number yet: add one to the result if you're sure of it.")
    return notes


def load_bank(path=None):
    """Your saved answers, as a list. An empty list if there's no file yet."""
    path = Path(path or BANK)  # BANK unless a test gives another path
    if not path.exists():
        return []
    return json.loads(path.read_text())


def save_answer(question, answer, path=None):
    """Add one answer to your bank and return how many answers it now holds."""
    path = Path(path or BANK)
    answers = load_bank(path)
    answers.append(
        {"question": question, "answer": answer, "saved": date.today().isoformat()}
    )
    path.parent.mkdir(parents=True, exist_ok=True)  # make private/ if it's missing
    path.write_text(json.dumps(answers, indent=2))
    return len(answers)