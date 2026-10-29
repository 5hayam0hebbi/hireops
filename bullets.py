# bullets.py - suggest resume bullets for a job, using ONLY what the resume already says
import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from ai import ask  # one place that talks to the model, with a time limit
from evidence import numbered_lines  # the same line numbers the meaning check uses
from matcher import mentions, stem


# One bullet idea from the AI: the sentence, and the number of the resume line it is
# based on. Asking for the line makes the AI build on a real fact, and lets the code
# check that the bullet really says what that line says.
class BulletIdea(BaseModel):
    text: str = Field(max_length=400)
    line: int


class Bullets(BaseModel):
    bullets: list[BulletIdea] = Field(max_length=5)  # at most 5, so it can't go on forever


# What suggest_bullets() gives back: the bullet, and YOUR resume line it came from
@dataclass
class Suggestion:
    text: str
    source: str


PROMPT = """You help a job seeker tailor their resume honestly.
Write exactly 3 NEW resume bullets for the job below.
Each bullet is ONE achievement sentence of 12 to 30 words. Start it with an action verb
(for example Led, Built, Reduced, Automated, Negotiated) and show a skill the job asks for.
Never return a job title, a heading, a company name or a date on its own.
Use ONLY experience that is stated in the resume.
Never invent employers, tools, numbers or achievements.
Base each bullet on ONE numbered resume line and give that line's number as "line".
Keep the line's numbers with the work they describe, and never move a number from
one line to another line's achievement.
Never upgrade what was done (for example "fixed" must not become "automated").
Use the job's wording where the resume truly supports it.
{focus}
Job description:
{job}

Numbered resume:
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


# Small words that don't tell you what a line is about
STOP_WORDS = {
    "a", "an", "and", "the", "of", "to", "in", "on", "for", "with", "by", "from",
    "at", "as", "into", "across", "that", "this", "it", "its", "is", "was", "were",
    "be", "or", "our", "their", "all", "every", "each", "per", "over", "than",
}

# Claims a rewrite must not add. If a bullet says "automated" but the resume line it
# came from never does, the AI has upgraded what you did. Keys are word starts.
CLAIM_WORDS = {
    "automat": "automated",
    "architect": "architected",
    "design": "designed",
}


def metrics_in(text: str) -> set[str]:
    """Numbers that are amounts (35, 99.9, 200), not labels like the 2 in "P2"."""
    # (?<![A-Za-z]) = "not right after a letter"; (?:\.\d+)? = an optional decimal part
    return set(re.findall(r"(?<![A-Za-z\d.])\d+(?:\.\d+)?", text))


def content_words(text: str) -> set[str]:
    """The meaningful words in a text, lowercased (no small words, no numbers)."""
    words = re.findall(r"[a-z][a-z0-9+#/-]*", text.lower())
    return {w for w in words if w not in STOP_WORDS and len(w) > 2}


# Everyday resume words: a bullet may add these without claiming anything new
GENERIC = {
    "led", "lead", "leading", "built", "build", "developed", "develop", "designed",
    "implemented", "created", "improved", "reduced", "increased", "managed", "delivered",
    "drove", "established", "scaled", "ensured", "using", "utilizing", "used", "across",
    "resulting", "including", "through", "while", "team", "teams", "multiple", "new",
    "strong", "effective", "efficient", "key", "critical", "enterprise", "solutions",
}

# A bullet must share at least this many meaningful words with its source line
MIN_SHARED = 3


def borrowed_words(bullet: str, resume_text: str, job_text: str) -> list[str]:
    """Words in the bullet that the job uses but your resume never does.

    This is how a tailored bullet invents a claim: it copies the job's words
    ("Talent Acquisition", "AI model performance") onto your experience.
    """
    resume = {stem(word) for word in re.findall(r"[a-z0-9+#]+", resume_text.lower())}
    job = {stem(word) for word in re.findall(r"[a-z0-9+#]+", job_text.lower())}
    found = []
    for word in sorted(content_words(bullet) - GENERIC):
        root = stem(word)
        if root in job and root not in resume and word not in found:
            found.append(word)
    return found


def source_line(bullet: str, resume_text: str) -> str:
    """The resume line the bullet most likely came from (the most shared words)."""
    lines = [line.strip(" -•*") for line in resume_text.splitlines() if line.strip()]
    if not lines:
        return ""
    words = content_words(bullet)
    # max(..., key=...) picks the line with the most words in common with the bullet
    return max(lines, key=lambda line: len(words & content_words(line)))


def bullet_warnings(
    bullet: str,
    resume_text: str,
    gaps: list[str],
    line: str = "",
    job_text: str = "",
) -> list[str]:
    """Plain-English problems with a suggested bullet. An empty list = no problems found.

    line = the resume line the AI said the bullet is based on (guessed if empty).
    1. Numbers from another line: every number must be on the bullet's source line,
       so "90%" (self-healing) can't be glued to "35%" (runbooks).
    2. Upgraded claims: "automated" only if the source line says so.
    3. Real gaps: a bullet must not name a skill your resume doesn't show.
    4. Borrowed claims: words taken from the job that your resume never uses.
    """
    warnings = []
    line = line or source_line(bullet, resume_text)
    resume_numbers = metrics_in(resume_text)
    for number in sorted(metrics_in(bullet)):
        # Numbers not in the resume at all are reported by unsupported_numbers()
        if number in resume_numbers and number not in metrics_in(line):
            warnings.append(
                f"{number} comes from a different resume line, not the one this bullet is about"
            )
    bullet_low, line_low = bullet.lower(), line.lower()
    for start in CLAIM_WORDS:
        # \w* = the rest of the word, so "automat" finds "automation" or "automated"
        found = re.search(r"\b" + start + r"\w*", bullet_low)
        if found and start not in line_low:
            warnings.append(f'says "{found.group()}", but your resume line doesn\'t')
    for skill in gaps:
        if mentions(bullet, skill):
            warnings.append(f"names {skill}, which your resume doesn't show")
    if job_text:
        borrowed = borrowed_words(bullet, resume_text, job_text)
        if borrowed:
            words = ", ".join(f'"{w}"' for w in borrowed)
            warnings.append(f"uses {words} from the job, but your resume never does")
    return warnings


def looks_like_bullet(bullet: str, resume_text: str) -> bool:
    """A real bullet is a sentence of 8+ words, not a line copied from the resume."""
    resume_lines = [line.strip(" -•*").lower() for line in resume_text.splitlines()]
    copied = bullet.strip(" -•*").lower() in resume_lines
    return len(bullet.split()) >= 8 and not copied


def suggest_bullets(
    job_text: str, resume_text: str, focus: list[str] | None = None, tries: int = 2
) -> list[Suggestion]:
    """Ask the local model for 3 tailored bullets, each tied to one of your lines.

    focus = the job's must-haves, so the bullets aim at what this job cares about.
    A bullet is dropped if it isn't a real bullet, names a line that doesn't exist,
    or shares fewer than MIN_SHARED meaningful words with that line.
    """
    lines, numbered = numbered_lines(resume_text)
    aim = ""
    if focus:
        aim = (
            "Aim the bullets at these must-haves, where the resume truly shows them: "
            + ", ".join(focus)
            + "\n"
        )
    prompt = PROMPT.format(job=job_text, resume=numbered, focus=aim)
    for _ in range(tries):  # small models sometimes return titles; ask once more if so
        # temperature 0.4 adds a little variety, so a second try can differ
        ideas = ask(prompt, Bullets, temperature=0.4).bullets
        good = []
        for idea in ideas:
            if not looks_like_bullet(idea.text, resume_text):
                continue  # a job title or a copied line
            if not 1 <= idea.line <= len(lines):
                continue  # points at a line that doesn't exist
            source = lines[idea.line - 1].strip(" -•*")  # without the bullet mark
            if len(content_words(idea.text) & content_words(source)) < MIN_SHARED:
                continue  # says something its source line doesn't
            good.append(Suggestion(text=idea.text, source=source))
        if good:
            return good
    return []
