# bullets.py - suggest resume bullets for a job, using ONLY what the resume already says
import re

from pydantic import BaseModel, Field

from ai import ask  # one place that talks to the model, with a time limit


class Bullets(BaseModel):
    bullets: list[str] = Field(max_length=5)  # at most 5, so it can't go on forever


PROMPT = """You help a job seeker tailor their resume honestly.
Write exactly 3 NEW resume bullets for the job below.
Each bullet is ONE achievement sentence of 12 to 30 words. Start it with an action verb
(for example Led, Built, Reduced, Automated, Negotiated) and show a skill the job asks for.
Never return a job title, a heading, a company name or a date on its own.
Use ONLY experience that is stated in the resume.
Never invent employers, tools, numbers or achievements.
Use the job's wording where the resume truly supports it.

Job description:
{job}

Resume:
{resume}"""


def numbers_in(text: str) -> set[str]:
    """Every number in the text, as a set (a collection with no duplicates)."""
    # \d means "a digit"; + means "one or more", so \d+ matches 25, 300, 2026...
    # re.findall() returns every match as a list; set() removes duplicates
    return set(re.findall(r"\d+", text))


def unsupported_numbers(bullet: str, resume_text: str) -> set[str]:
    """Numbers in a bullet that never appear in the resume: a sign of invention."""
    # For sets, a - b means "items in a that are not in b"
    return numbers_in(bullet) - numbers_in(resume_text)


def looks_like_bullet(bullet: str, resume_text: str) -> bool:
    """A real bullet is a sentence of 8+ words, not a line copied from the resume."""
    resume_lines = [line.strip(" -•*").lower() for line in resume_text.splitlines()]
    copied = bullet.strip(" -•*").lower() in resume_lines
    return len(bullet.split()) >= 8 and not copied


def suggest_bullets(job_text: str, resume_text: str, tries: int = 2) -> list[str]:
    """Ask the local model for 3 tailored bullets; drop any that aren't real bullets."""
    prompt = PROMPT.format(job=job_text, resume=resume_text)
    for _ in range(tries):  # small models sometimes return titles; ask once more if so
        # temperature 0.4 adds a little variety, so a second try can differ
        bullets = ask(prompt, Bullets, temperature=0.4).bullets
        # Keep only the ones that pass the check (a job title copied back is dropped)
        good = [b for b in bullets if looks_like_bullet(b, resume_text)]
        if good:
            return good
    return []
