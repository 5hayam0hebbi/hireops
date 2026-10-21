# matcher.py - find which skills a text mentions, using regular expressions
import re  # Python's built-in regular expression module
from dataclasses import dataclass

# Other ways people write the same skill. Keys are skills in lowercase; values are aliases.
ALIASES = {
    "kubernetes": ["k8s"],
    "leadership": ["led a team", "managed a team", "people leader"],
    "sre": ["site reliability"],
    "incident management": ["incident response"],
}


def skill_pattern(skill: str) -> str:
    """Build a pattern that matches the skill as a whole word."""
    # re.escape() makes characters like / . + match literally, so "CI/CD" is safe.
    # \b means "word boundary": the edge between a letter and a non-letter.
    # s? means "an optional s", so "SLO" also matches "SLOs".
    # The r before the quotes makes a raw string, so the backslash stays a backslash.
    return r"\b" + re.escape(skill) + r"s?\b"


def mentions(text: str, skill: str) -> bool:
    """True if the text mentions the skill as a whole word, in any letter case."""
    # The skill itself, plus its aliases (.get gives [] if the skill has none).
    # skill.lower() finds the aliases whether the skill is written "Leadership" or "leadership".
    names = [skill] + ALIASES.get(skill.lower(), [])
    for name in names:
        # re.search() looks anywhere in the text; it returns None when there's no match
        if re.search(skill_pattern(name), text, re.IGNORECASE):
            return True
    return False


def find_skills(text: str, skills: list[str]) -> list[str]:
    """Return the skills from the list that the text mentions."""
    return [skill for skill in skills if mentions(text, skill)]


# @dataclass writes the boring parts of a class for you (like __init__),
# so MatchResult(wanted=[...], have=[...]) just works.
@dataclass
class MatchResult:
    """How well a resume covers the skills a job asks for."""

    wanted: list[str]  # skills the job asks for
    have: list[str]  # of those, the ones the resume mentions

    # A method is a function that belongs to the class; self is the object itself
    def missing(self) -> list[str]:
        """Skills the job wants that the resume never mentions."""
        return [skill for skill in self.wanted if skill not in self.have]

    def score(self) -> int:
        """Percentage of the job's skills the resume mentions (0 if none wanted)."""
        if not self.wanted:
            return 0
        return round(len(self.have) / len(self.wanted) * 100)


def match(job_text: str, resume_text: str, skills: list[str]) -> MatchResult:
    """Compare a job and a resume against your skills list."""
    wanted = find_skills(job_text, skills)
    have = find_skills(resume_text, wanted)  # only check what this job wants
    return MatchResult(wanted=wanted, have=have)
