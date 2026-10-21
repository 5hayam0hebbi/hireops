# edits.py - suggest changes to your resume for one job: modify, add or remove
# Each AI request is small and simple, so a small local model can do it reliably.
import re

from pydantic import BaseModel, Field

from ai import ask  # one place that talks to the model, with a time limit
from bullets import unsupported_numbers
from evidence import numbered_lines
from matcher import find_skills


# The answer to "rewrite this one line": just the new line
class Rewrite(BaseModel):
    new_line: str = Field(max_length=300)


# One line the AI thinks this job doesn't need, and why
class Removal(BaseModel):
    line: int
    reason: str = Field(max_length=200)


class Removals(BaseModel):
    remove: list[Removal] = Field(max_length=3)  # a cap, so it can't go on forever


REWRITE_PROMPT = """Rewrite this ONE resume line so it clearly names the skill "{skill}",
using the job's own words for it. Keep every fact, tool and number that is in the line.
Do not add new facts, tools or numbers. Reply with the new line only.

Resume line:
{line}"""

REMOVE_PROMPT = """The resume's lines are numbered. Pick up to 2 lines that matter least
for the job below (for example old or unrelated technology) and could be cut to save
space. Never pick a name, contact detail, job title, employer or date line.
Give each line's number and a short reason.

Job description:
{job}

Numbered resume:
{resume}"""


def rewrite_is_useful(old: str, new: str, skill: str) -> bool:
    """A useful rewrite is different from the old line and passes the word check."""
    changed = new.strip().lower() != old.strip().lower()
    # the same rule as the match score, so the rewrite would really raise your score
    names_skill = bool(find_skills(new, [skill]))
    return changed and names_skill and len(new.split()) >= 3


def names_in(line: str) -> set[str]:
    """Capitalized words (often tools or companies), skipping the line's first word."""
    # [A-Z][A-Za-z0-9+#.-]+ means "a capital letter, then letters, digits or + # . -"
    words = re.findall(r"\b[A-Z][A-Za-z0-9+#.-]+|\b\w+", line)
    first_word = words[:1]  # "Led", "Built"... are capitalized only because they start
    return {w for w in words if w[0].isupper() and w not in first_word}


def new_names(new: str, resume_text: str, skill: str) -> set[str]:
    """Capitalized words in the rewrite that the resume never mentions."""
    known = resume_text.lower() + " " + skill.lower()  # the skill is meant to be new
    return {name for name in names_in(new) if name.lower() not in known}


def dropped_names(old: str, new: str) -> set[str]:
    """Capitalized words in your line that the rewrite left out (facts it dropped)."""
    return {name for name in names_in(old) if name.lower() not in new.lower()}


def real_removals(removals: list[Removal], lines: list[str]) -> list[Removal]:
    """Keep only removals that point to a line the resume really has."""
    return [r for r in removals if 1 <= r.line <= len(lines)]


def suggest_edits(
    job_text: str, resume_text: str, missing: list[str], by_meaning: dict[str, str]
) -> list[dict]:
    """Return suggested edits, each with YOUR original line and any invented numbers."""
    results = []

    # MODIFY: a line that may show a missing skill gets rewritten to name it
    for skill, line in list(by_meaning.items())[:5]:  # at most 5, to keep it quick
        prompt = REWRITE_PROMPT.format(skill=skill, line=line)
        new = ask(prompt, Rewrite, temperature=0.3).new_line
        if rewrite_is_useful(line, new, skill):
            results.append(
                {
                    "action": "modify",
                    "before": line,  # copied by the code, so it's always real
                    "after": new.strip(),
                    "reason": f"names {skill} in the job's words",
                    # numbers and names the AI added that your resume never mentions
                    "invented": sorted(
                        unsupported_numbers(new, resume_text)
                        | new_names(new, resume_text, skill)  # | joins two sets
                    ),
                    "dropped": sorted(dropped_names(line, new)),
                }
            )

    # ADD: missing skills with no line at all; plain rules, no AI needed
    for skill in missing:
        if skill not in by_meaning:
            results.append(
                {
                    "action": "add",
                    "before": "",
                    "after": skill,
                    "reason": "the job asks for it; add it ONLY if you really have it",
                    "invented": [],
                    "dropped": [],
                }
            )

    # REMOVE: lines this job doesn't need, picked by the AI by line number
    lines, numbered = numbered_lines(resume_text)
    prompt = REMOVE_PROMPT.format(job=job_text, resume=numbered)
    for removal in real_removals(ask(prompt, Removals).remove, lines):
        results.append(
            {
                "action": "remove",
                "before": lines[removal.line - 1],  # YOUR line, copied by the code
                "after": "",
                "reason": removal.reason.strip(),
                "invented": [],
                "dropped": [],
            }
        )
    return results
