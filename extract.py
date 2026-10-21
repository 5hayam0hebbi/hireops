# extract.py - ask a local AI model to read a job description for meaning
from pydantic import BaseModel, Field

from ai import ask  # one place that talks to the model, with a time limit

# Field(max_length=...) caps a text's characters (or, on a list, its items). Ollama
# passes the caps to the model, and pydantic rejects an answer that breaks them.


# One red flag: a short concern, and the exact words in the posting that raise it
class RedFlag(BaseModel):
    concern: str = Field(max_length=80)
    quote: str = Field(max_length=200)


# A class is a blueprint. Inheriting from BaseModel (the brackets) gives JobInsights
# pydantic's powers: it can describe its own shape and check data against it.
class JobInsights(BaseModel):
    role_title: str
    seniority: str  # junior, mid, senior, lead or executive
    years_experience: int | None = None  # None (null in JSON) when not stated
    skills: list[str] = Field(max_length=30)  # the posting's skills, found by the AI
    must_haves: list[str] = Field(max_length=12)
    nice_to_haves: list[str] = Field(max_length=10)
    red_flags: list[RedFlag] = Field(max_length=5)


PROMPT = """You are a careful, honest recruiter. Read the job description and reply in JSON.
role_title: the job title.
seniority: one of junior, mid, senior, lead, executive.
years_experience: the minimum years of experience asked for, or null if not stated.
skills: every skill, tool, technology, method or competency the posting asks for,
each as a short name of 1 to 3 words, for example "Kubernetes", "Terraform",
"incident management", "stakeholder communication". No duplicates.
must_haves: skills or experience the posting clearly requires (short phrases).
nice_to_haves: things described as a plus, preferred or bonus.
red_flags: only things in THIS posting a candidate should ask about. For each one give
"concern" (a few words) and "quote" (the exact words copied from the posting that raise it).
Use an empty list if nothing in this posting is concerning.
Use only what the text says. Use an empty list when there is nothing to report.

Job description:
{job}"""


def normalize(text: str) -> str:
    """Lowercase and squeeze spaces, so small differences don't break a comparison."""
    return " ".join(text.lower().split())


def quoted_flags(flags: list[RedFlag], job_text: str) -> list[RedFlag]:
    """Keep only red flags whose quote really appears in the posting."""
    posting = normalize(job_text)
    return [f for f in flags if f.quote.strip() and normalize(f.quote) in posting]


def unique(items: list[str]) -> list[str]:
    """Remove repeats, ignoring letter case, and keep the original order."""
    seen = set()  # a set remembers what we've already kept
    result = []
    for item in items:
        key = item.strip().lower()  # "Python " and "python" count as the same
        if key and key not in seen:
            seen.add(key)
            result.append(item.strip())
    return result


def extract(job_text: str) -> JobInsights:
    """Return the job's title, seniority, skills, must-haves and red flags."""
    # ask() fills in a JobInsights object (temperature 0 = as repeatable as possible)
    insights = ask(PROMPT.format(job=job_text), JobInsights)
    insights.skills = unique(insights.skills)  # tidy the AI's list
    # A red flag without real words from the posting is a guess, so drop it
    insights.red_flags = quoted_flags(insights.red_flags, job_text)
    return insights
