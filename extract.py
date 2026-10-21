# extract.py - ask a local AI model to read a job description for meaning
import ollama
from pydantic import BaseModel

MODEL = "llama3.2"


# A class is a blueprint. Inheriting from BaseModel (the brackets) gives JobInsights
# pydantic's powers: it can describe its own shape and check data against it.
class JobInsights(BaseModel):
    role_title: str
    seniority: str  # junior, mid, senior, lead or executive
    years_experience: int | None = (
        None  # None (null in JSON) when the posting doesn't say
    )
    skills: list[str]  # every skill the posting asks for, found by the AI
    must_haves: list[str]
    nice_to_haves: list[str]
    red_flags: list[str]


PROMPT = """You are a careful, honest recruiter. Read the job description and reply in JSON.
role_title: the job title.
seniority: one of junior, mid, senior, lead, executive.
years_experience: the minimum years of experience asked for, or null if not stated.
skills: every skill, tool, technology, method or competency the posting asks for,
each as a short name of 1 to 3 words, for example "Kubernetes", "Terraform",
"incident management", "stakeholder communication". No duplicates.
must_haves: skills or experience the posting clearly requires (short phrases).
nice_to_haves: things described as a plus, preferred or bonus.
red_flags: things a candidate should ask about, such as vague scope or unrealistic demands.
Use only what the text says. Use an empty list when there is nothing to report.

Job description:
{job}"""


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
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": PROMPT.format(job=job_text)}],
        format=JobInsights.model_json_schema(),  # the exact JSON shape we want
        options={"temperature": 0},  # 0 = as repeatable as possible
    )
    # Check the model's JSON against the blueprint and build a JobInsights object
    insights = JobInsights.model_validate_json(response.message.content)
    insights.skills = unique(insights.skills)  # tidy the AI's list
    return insights
