# extract.py - ask a local AI model to read a job description for meaning
import re
from typing import Literal

from pydantic import BaseModel, Field

from ai import ask  # one place that talks to the model, with a time limit
from matcher import core_words, stem

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
requirements: everything THIS posting judges a candidate on: tools and technologies,
and also leadership, people and experience requirements. Name each one with the
posting's own words, 1 to 4 words. Never add anything the posting doesn't mention.
Never use an umbrella name such as "technical skills" or "leadership experience".
Put the importance only in the importance field, never inside the name.
If the posting lists its tools but says experience in them is not needed, still list
each tool, as "not required".
Give each an importance:
  "must-have" = the posting requires it or lists it under what you need to bring,
  "nice-to-have" = described as a plus, preferred or bonus,
  "not required" = the posting names it but says experience in it is NOT needed
  (for example "we don't require previous experience in our stack").
No duplicates.
red_flags: only real concerns in THIS posting, for example pay far below the level,
an unrealistic scope, or a contract described as permanent. The normal duties of the
role, standard policies and legal or HR wording are NOT red flags. For each one give
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

# Umbrella words. A requirement made ONLY of these ("Technical Skills", "Leadership
# Experience") matches almost any resume, so it would fake a high score: we drop it.
VAGUE_WORDS = {
    "technical", "skills", "skill", "leadership", "experience", "soft", "general",
    "relevant", "professional", "communication", "strong", "good", "excellent",
}


# Labels the AI sometimes writes into a name: "Azure administration (must-have)"
LABEL = re.compile(
    r"\s*[(\[]\s*(must[- ]have|nice[- ]to[- ]have|not required|required|preferred|"
    r"optional|bonus)\s*[)\]]",
    re.IGNORECASE,
)

# Wording every posting from a big employer carries. A "red flag" quoting it isn't one.
BOILERPLATE = [
    "risk management framework",
    "risk appetite",
    "measured risk",
    "may be assigned as needed",
    "other duties as assigned",
    "equal opportunity",
    "accommodation",
    "criminal record check",
    "background check",
]


def clean_name(name: str) -> str:
    """Remove importance labels from a requirement's name, and tidy the spaces."""
    return " ".join(LABEL.sub("", name).split())


def in_posting(name: str, job_text: str) -> bool:
    """True if every core word of the name appears in the posting (roughly).

    A requirement the posting never mentions was made up by the AI.
    """
    posting = {stem(word) for word in re.findall(r"[a-z0-9+#]+", job_text.lower())}
    words = core_words(name)
    return bool(words) and all(stem(word) in posting for word in words)


def is_vague(name: str) -> bool:
    """True if every word of the name is an umbrella word."""
    words = re.findall(r"[a-z]+", name.lower())
    return bool(words) and all(word in VAGUE_WORDS for word in words)


# Curly quotes from web pages and Word, mapped to plain ones: don’t -> don't
STRAIGHT = str.maketrans({"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"'})


def normalize(text: str) -> str:
    """Lowercase, straighten quotes and squeeze spaces, so small differences don't
    break a comparison."""
    return " ".join(text.translate(STRAIGHT).lower().split())


def quoted_flags(flags: list[RedFlag], job_text: str) -> list[RedFlag]:
    """Keep only red flags whose quote really appears in the posting, minus boilerplate."""
    posting = normalize(job_text)
    kept = []
    for flag in flags:
        quote = normalize(flag.quote)
        if not quote or quote not in posting:
            continue  # the AI invented the quote
        if any(phrase in quote for phrase in BOILERPLATE):
            continue  # standard wording, not a concern about this job
        kept.append(flag)
    return kept


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
    """Fix the AI's labels with rules, because the posting's own words beat a guess.

    - Labels inside names ("Azure (must-have)") are removed.
    - Umbrella names ("Technical Skills"), repeats and anything the posting never
      mentions ("hands-on coding" when the posting doesn't say coding) are dropped.
    - "not required" only when the posting says so next to the skill; otherwise
      the AI guessed, so it goes back to "must-have" (safer to check than to skip).
    """
    seen = set()
    fixed = []
    for req in requirements:
        name = clean_name(req.name)
        key = name.lower()
        if not key or key in seen or is_vague(name) or not in_posting(name, job_text):
            continue
        seen.add(key)
        importance = req.importance
        if said_not_needed(name, job_text):
            importance = "not required"
        elif importance == "not required":
            importance = "must-have"
        fixed.append(Requirement(name=name, importance=importance))
    return fixed


def extract(job_text: str) -> JobInsights:
    """Return the job's title, seniority, labelled requirements and red flags."""
    # ask() fills in a JobInsights object (temperature 0 = as repeatable as possible)
    insights = ask(PROMPT.format(job=job_text), JobInsights)
    insights.requirements = apply_text_rules(insights.requirements, job_text)
    # A red flag without real words from the posting is a guess, so drop it
    insights.red_flags = quoted_flags(insights.red_flags, job_text)
    return insights
