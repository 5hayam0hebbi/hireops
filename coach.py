# coach.py - Interview Coach's engine: likely questions for a job, and STAR feedback
from typing import Literal

from pydantic import BaseModel, Field

from ai import AIError, ask
from decoder import decode, say_nothing
from matcher import mentions


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
    for skill in skills[:5]:
        text = f"Tell me about a time you used {skill} to solve a real problem."
        questions.append(Question(text=text, kind="behavioural", skill=skill))
    for skill in skills[5:8]:
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