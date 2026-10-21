# evidence.py - ask the AI whether your resume shows a skill in other words, with proof
from pydantic import BaseModel, Field

from ai import ask  # one place that talks to the model, with a time limit


# One answer: a skill and the number of the resume line that proves it (0 = none)
class Evidence(BaseModel):
    skill: str
    line: int


# The whole answer: a list of Evidence objects
class EvidenceList(BaseModel):
    found: list[Evidence] = Field(max_length=40)  # a cap, so it can't go on forever


PROMPT = """You check resumes honestly. The resume's lines are numbered.
For each skill below, find ONE line that shows the person has that skill, even in
different words (for example "Built monitoring with Dynatrace" shows observability).
Answer with that line's number. Use 0 when no line shows the skill. Never guess.

Skills:
{skills}

Numbered resume:
{resume}"""


def normalize(text):
    """Lowercase and squeeze spaces, so small differences don't break the check."""
    # .split() breaks the text into words; " ".join puts them back with single spaces
    return " ".join(text.lower().split())


def verified(quote, resume_text):
    """True only if the quote really appears in the resume: the AI can't invent proof."""
    return bool(quote.strip()) and normalize(quote) in normalize(resume_text)


def numbered_lines(resume_text):
    """The resume's non-empty lines, and the same lines as numbered text for the AI."""
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    # enumerate(..., start=1) counts 1, 2, 3... alongside each line
    text = "\n".join(f"{number}: {line}" for number, line in enumerate(lines, start=1))
    return lines, text


def find_by_meaning(missing, resume_text):
    """For skills the word check missed, return {skill: resume line} the AI points to."""
    if not missing:  # nothing to check, so don't call the AI
        return {}
    lines, numbered = numbered_lines(resume_text)
    prompt = PROMPT.format(skills="\n".join(missing), resume=numbered)
    answer = ask(prompt, EvidenceList)

    # Look up our own spelling of each skill, whatever letter case the AI used
    by_lowercase = {skill.lower(): skill for skill in missing}
    proven = {}
    for item in answer.found:
        skill = by_lowercase.get(item.skill.strip().lower())
        # Keep it only if we asked about this skill AND the line number really exists.
        # The proof shown is YOUR line, copied by the code, so the AI can't invent it.
        if skill and 1 <= item.line <= len(lines):
            proven[skill] = lines[item.line - 1]
    return proven
