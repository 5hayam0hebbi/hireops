# extract.py - ask a local AI model to read a job description for meaning
import re
from typing import Literal

from pydantic import BaseModel, Field

from ai import ask  # one place that talks to the model, with a time limit

# Field(max_length=...) caps a text's characters (or, on a list, its items). Ollama
# passes the caps to the model, and pydantic rejects an answer that breaks them.


# One red flag: a short concern, and the exact words in the posting that raise it
class RedFlag(BaseModel):
    concern: str = Field(max_length=80)
    quote: str = Field(max_length=200)


# One thing the job asks for, and how much it matters.
# Literal[...] means the value must be one of these exact words, nothing else.
Importance = Literal["must-have", "nice-to-have", "not required"]


class Requirement(BaseModel):
    name: str = Field(max_length=80)  # short name, e.g. "Kubernetes", "hiring"
    importance: Importance


# A class is a blueprint. Inheriting from BaseModel (the brackets) gives JobInsights
# pydantic's powers: it can describe its own shape and check data against it.
class JobInsights(BaseModel):
    role_title: str
    seniority: str  # junior, mid, senior, lead or executive
    years_experience: int | None = None  # None (null in JSON) when not stated
    requirements: list[Requirement] = Field(max_length=30)
    red_flags: list[RedFlag] = Field(max_length=5)

    # @property turns a method into a value you read without (): insights.must_haves
    @property
    def must_haves(self) -> list[str]:
        return [r.name for r in self.requirements if r.importance == "must-have"]

    @property
    def nice_to_haves(self) -> list[str]:
        return [r.name for r in self.requirements if r.importance == "nice-to-have"]

    @property
    def not_required(self) -> list[str]:
        """Things the posting names but says you don't need (e.g. its tech stack)."""
        return [r.name for r in self.requirements if r.importance == "not required"]

    @property
    def skills(self) -> list[str]:
        """What we score your resume on: must-haves first, then nice-to-haves."""
        return self.must_haves + self.nice_to_haves


PROMPT = """You are a careful, honest recruiter. Read the job description and reply in JSON.
role_title: the job title.
seniority: one of junior, mid, senior, lead, executive.
years_experience: the minimum years of experience asked for, or null if not stated.
requirements: everything a candidate is judged on. Include technical skills AND
leadership, people and experience requirements (for example "hiring", "coaching
engineers", "hands-on coding", "stakeholder communication", "led platform teams").
Give each a short name of 1 to 4 words and an importance:
  "must-have" = the posting requires it or lists it under what you need to bring,
  "nice-to-have" = described as a plus, preferred or bonus,
  "not required" = the posting names it but says experience in it is NOT needed
  (for example "we don't require previous experience in our stack").
No duplicates.
red_flags: only things in THIS posting a candidate should ask about. For each one give
"concern" (a few words) and "quote" (the exact words copied from the posting that raise it).
Use an empty list if nothing in this posting is concerning.
Use only what the text says. Use an empty list when there is nothing to report.

Job description:
{job}"""

# Words that mean "you don't need this". If a skill sits in the same paragraph as one
# of these, the code marks it "not required", whatever the AI said.
NOT_NEEDED = [
    "don't require",
    "do not require",
    "doesn't require",
    "not required",
    "no prior experience",
    "no previous experience",
    "don't need",
    "do not need",
    "don't worry if you don't know",
]


def normalize(text: str) -> str:
    """Lowercase and squeeze spaces, so small differences don't break a comparison."""
    return " ".join(text.lower().split())


def quoted_flags(flags: list[RedFlag], job_text: str) -> list[RedFlag]:
    """Keep only red flags whose quote really appears in the posting."""
    posting = normalize(job_text)
    return [f for f in flags if f.quote.strip() and normalize(f.quote) in posting]


def paragraphs(text: str) -> list[str]:
    """The text split at blank lines (or single lines, if there are no blank lines)."""
    parts = re.split(r"\n\s*\n", text)
    if len(parts) == 1:
        parts = text.splitlines()
    return [normalize(part) for part in parts if part.strip()]


def said_not_needed(name: str, job_text: str) -> bool:
    """True if the posting names this skill in a paragraph that says it isn't needed."""
    key = normalize(name)
    for part in paragraphs(job_text):
        # \b = word boundary, so "React" doesn't match inside "Reactive"
        named = re.search(r"\b" + re.escape(key) + r"\b", part)
        if named and any(phrase in part for phrase in NOT_NEEDED):
            return True
    return False


def apply_text_rules(requirements: list[Requirement], job_text: str) -> list[Requirement]:
    """Fix the AI's labels with rules: 'not required' wording wins; repeats go."""
    seen = set()
    fixed = []
    for req in requirements:
        key = req.name.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        importance = req.importance
        if said_not_needed(req.name, job_text):
            importance = "not required"
        fixed.append(Requirement(name=req.name.strip(), importance=importance))
    return fixed


def extract(job_text: str) -> JobInsights:
    """Return the job's title, seniority, labelled requirements and red flags."""
    # ask() fills in a JobInsights object (temperature 0 = as repeatable as possible)
    insights = ask(PROMPT.format(job=job_text), JobInsights)
    insights.requirements = apply_text_rules(insights.requirements, job_text)
    # A red flag without real words from the posting is a guess, so drop it
    insights.red_flags = quoted_flags(insights.red_flags, job_text)
    return insights
