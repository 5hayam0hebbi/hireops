# evidence.py - ask the AI whether your resume shows a skill in other words, with proof
import re

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
Sharing a word is not proof: "10 vendor providers" does not show "cloud providers".
A named tool (AWS, GCP, TypeScript...) is shown only by a line that names it.

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


def named_tools(skill):
    """Product names a skill depends on: "Cloud Providers (AWS, GCP)" -> ["AWS", "GCP"].

    A tool name can't be shown "in other words": a resume shows AWS only by naming
    AWS. Names come from brackets, or from a one-word skill with capitals or digits
    (for example "TypeScript", "Postgres", "AZ-104").
    """
    inside = re.findall(r"\(([^)]*)\)", skill)  # the text between ( and )
    if inside:
        names = re.split(r"[,/]| or | and ", " ".join(inside))
        return [name.strip() for name in names if name.strip()]
    word = skill.strip()
    if " " not in word and re.search(r"[A-Z0-9]", word[1:]):  # e.g. TypeScript, EC2
        return [word]
    return []


def proves(skill, line):
    """True if a resume line can count as proof of the skill.

    For a skill built on named tools, the line must name at least one of them.
    """
    names = named_tools(skill)
    if not names:
        return True  # a general skill: the AI's reading is allowed
    return any(re.search(r"\b" + re.escape(name) + r"\b", line, re.IGNORECASE)
               for name in names)


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
        # proves() stops a line like "10 vendor providers" counting as AWS experience.
        if skill and 1 <= item.line <= len(lines):
            line = lines[item.line - 1]
            if proves(skill, line):
                proven[skill] = line
    return proven
