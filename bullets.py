# bullets.py - suggest resume bullets for a job, using ONLY what the resume already says
import re

import ollama
from pydantic import BaseModel

MODEL = "llama3.2"


class Bullets(BaseModel):
    bullets: list[str]


PROMPT = """You help a job seeker tailor their resume honestly.
Write exactly 3 resume bullets for the job below.
Rules:
- Use ONLY experience that is stated in the resume.
- Never invent employers, tools, numbers or achievements.
- Use the job's wording where the resume truly supports it.

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


def suggest_bullets(job_text: str, resume_text: str) -> list[str]:
    """Ask the local model for 3 tailored bullets."""
    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "user", "content": PROMPT.format(job=job_text, resume=resume_text)}
        ],
        format=Bullets.model_json_schema(),
        options={"temperature": 0.2},
    )
    return Bullets.model_validate_json(response.message.content).bullets
