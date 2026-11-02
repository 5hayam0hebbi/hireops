# resume_edit.py - add the bullets you chose to a NEW copy of your resume
# Your original file is never changed: every function here returns new text or bytes.
import re
from dataclasses import dataclass, field

# A bullet mark at the start of a line: -, *, • or –, then a space.
# ^ = "the start of the line"; \s* = "any spaces"; [...] = "one of these characters"
BULLET = re.compile(r"^\s*[-*•–]\s+")
# A year from 1900 to 2099, like 2019: job-title lines usually carry dates
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")


# One line of a resume: its words, and whether it is a bullet or a heading
@dataclass
class Line:
    text: str
    bullet: bool = False
    heading: bool = False


# One place you can add bullets: a heading or job-title line with bullets under it
@dataclass
class Place:
    start: int | None  # the line number of the heading; None = "at the very end"
    label: str  # what the page shows in the list
    lines: list[str] = field(default_factory=list)  # the bullets already there


def text_lines(text):
    """The lines of a .txt or .md resume (or the text read from a PDF)."""
    return [
        Line(line, bullet=bool(BULLET.match(line)), heading=line.startswith("#"))
        for line in text.splitlines()
    ]


def next_text(lines, i):
    """The number of the next line after line i that has words, or None."""
    for j in range(i + 1, len(lines)):
        if lines[j].text.strip():
            return j
    return None


def is_place(lines, i):
    """True if line i is a heading or a job-title line: a place bullets can go."""
    line = lines[i]
    text = line.text.strip()
    if not text or line.bullet:
        return False  # empty lines and bullets are never places
    if line.heading:
        return True  # "# Experience" in Markdown, or a Word heading style
    if len(text.split()) > 14 or text.endswith("."):
        return False  # a long line or a sentence is body text, not a title
    if text.isupper() or YEAR.search(text):
        return True  # "EXPERIENCE", or "Senior Manager | 2015 - 2020"
    following = next_text(lines, i)
    # A short line that introduces bullets: "Director, Site Reliability Engineering"
    return following is not None and lines[following].bullet

def section_end(lines, start, starts):
    """The last line with words in the section that starts at line `start`.

    starts = the line numbers of every place, so we know where the next one begins.
    """
    later = [s for s in starts if s > start]
    stop = later[0] if later else len(lines)  # the next place, or the end
    end = start
    for i in range(start + 1, stop):
        if lines[i].text.strip():
            end = i
    return end


def find_places(lines):
    """Every place with at least one bullet, plus "At the end" as the last choice."""
    starts = [i for i in range(len(lines)) if is_place(lines, i)]
    places = []
    for start in starts:
        body = lines[start + 1 : section_end(lines, start, starts) + 1]
        bullets = [BULLET.sub("", b.text).strip() for b in body if b.bullet]
        if bullets:  # only sections that already have bullets
            label = lines[start].text.strip().lstrip("#").strip()[:90]
            places.append(Place(start, label, bullets))
    places.append(Place(None, "At the end of the resume"))
    return places


def suggested(places, source):
    """The number (in places) of the section that holds the bullet's source line."""
    clean = BULLET.sub("", source).strip().lower()
    for number, place in enumerate(places):
        if clean in (line.lower() for line in place.lines):
            return number
    return 0  # not found: the first place


def add_to_text(text, start, bullets):
    """The text with the new bullets after the last line of the chosen section."""
    # Skip a bullet whose words are already in the resume, so nothing is added twice
    bullets = [b for b in bullets if b.lower() not in text.lower()]
    raw = text.splitlines()
    lines = text_lines(text)
    if start is None:  # "At the end of the resume"
        return "\n".join(raw + [f"- {b}" for b in bullets]) + "\n"
    starts = [i for i in range(len(lines)) if is_place(lines, i)]
    end = section_end(lines, start, starts)
    # Reuse the bullet mark (and indent) of the line above, like "- " or "• "
    found = BULLET.match(raw[end])
    mark = found.group() if found else "- "
    new = [mark + b for b in bullets]
    # raw[: end + 1] = every line up to and including end; then the new lines
    return "\n".join(raw[: end + 1] + new + raw[end + 1 :]) + "\n"
