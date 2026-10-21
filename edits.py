# edits.py - suggest changes to your resume lines for one job: modify, add or remove
from typing import Literal

from pydantic import BaseModel, Field

from ai import ask  # one place that talks to the model, with a time limit
from bullets import unsupported_numbers
from evidence import numbered_lines


# One suggested change. Literal[...] means the value must be one of these words.
class Edit(BaseModel):
    action: Literal["modify", "add", "remove"]
    line: int  # the resume line to modify or remove; 0 for add
    new_text: str = Field(max_length=300)  # the rewritten or added text; "" for remove
    reason: str = Field(max_length=200)  # why, in a few words


class Edits(BaseModel):
    edits: list[Edit] = Field(max_length=6)  # a cap, so it can't go on forever


PROMPT = """You are an honest resume coach. The resume's lines are numbered.
Suggest up to 5 changes that make this resume fit the job better.
- "modify": rewrite ONE existing line so it uses the job's words for something the
  line already shows. Give the line number and the full new line.
- "add": a short phrase to add to the skills or summary section (line 0), only for a
  skill the resume already shows in other words.
- "remove": a line that is not relevant to this job and takes up space. Give its number.
Focus first on these skills the resume doesn't name: {missing}
Never invent employers, tools, numbers or achievements. Keep every number unchanged.

Job description:
{job}

Numbered resume:
{resume}"""


def checked_edits(edits: list[Edit], lines: list[str]) -> list[Edit]:
    """Keep only edits that make sense: a real line to change, and real new text."""
    whole_resume = " ".join(lines).lower()
    kept = []
    for edit in edits:
        new = edit.new_text.strip()
        real_line = 1 <= edit.line <= len(lines)  # the line number exists
        if edit.action in ("modify", "remove") and not real_line:
            continue  # can't change a line that isn't there
        if edit.action == "modify" and (
            len(new.split()) < 3 or new == lines[edit.line - 1]
        ):
            continue  # too short to be a resume line, or "rewritten" to the same words
        if edit.action == "add" and (not new or new.lower() in whole_resume):
            continue  # nothing to add, or the resume already says it
        kept.append(edit)
    return kept


def suggest_edits(job_text: str, resume_text: str, missing: list[str]) -> list[dict]:
    """Return checked edits, each with your original line and any invented numbers."""
    lines, numbered = numbered_lines(resume_text)
    prompt = PROMPT.format(
        missing=", ".join(missing) or "none", job=job_text, resume=numbered
    )
    edits = checked_edits(ask(prompt, Edits).edits, lines)
    results = []
    for edit in edits:
        results.append(
            {
                "action": edit.action,
                # the code copies YOUR line, so the "before" text is always real
                "before": lines[edit.line - 1] if edit.action != "add" else "",
                "after": edit.new_text.strip(),
                "reason": edit.reason.strip(),
                # numbers the AI added that your resume never mentions
                "invented": sorted(unsupported_numbers(edit.new_text, resume_text)),
            }
        )
    return results
