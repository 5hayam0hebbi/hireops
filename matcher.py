# matcher.py - find which skills a text mentions, using regular expressions
import re  # Python's built-in regular expression module


def skill_pattern(skill: str) -> str:
    """Build a pattern that matches the skill as a whole word."""
    # re.escape() makes characters like / . + match literally, so "CI/CD" is safe.
    # \b means "word boundary": the edge between a letter and a non-letter.
    # s? means "an optional s", so "SLO" also matches "SLOs".
    # The r before the quotes makes a raw string, so the backslash stays a backslash.
    return r"\b" + re.escape(skill) + r"s?\b"


def mentions(text: str, skill: str) -> bool:
    """True if the text mentions the skill as a whole word, in any letter case."""
    # re.search() looks anywhere in the text; it returns None when there's no match
    return re.search(skill_pattern(skill), text, re.IGNORECASE) is not None


def find_skills(text: str, skills: list[str]) -> list[str]:
    """Return the skills from the list that the text mentions."""
    return [skill for skill in skills if mentions(text, skill)]