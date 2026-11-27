# resume_edit.py - add the bullets you chose to a NEW copy of your resume
# Your original file is never changed: every function here returns new text or bytes.
import re
from copy import deepcopy
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from docx import Document  # the python-docx package
from docx.oxml.ns import qn  # turns "w:pPr" into the full name Word's XML uses
from docx.text.paragraph import Paragraph

# A bullet mark at the start of a line: -, *, • or –, then a space.
# ^ = "the start of the line"; \s* = "any spaces"; [...] = "one of these characters"
BULLET = re.compile(r"^\s*[-*•–]\s+")
# A year from 1900 to 2099, like 2019: job-title lines usually carry dates
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")

# What each kind of file is called on the web, so the browser saves it correctly
MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "md": "text/markdown",
    "txt": "text/plain",
}


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


def docx_lines(document):
    """The paragraphs of a Word resume, in order (empty ones too, so the numbers
    match document.paragraphs exactly)."""
    lines = []
    for paragraph in document.paragraphs:
        style = paragraph.style.name if paragraph.style is not None else ""
        # A Word bullet is a "List" style, or a numbering setting (numPr) on the line
        p_pr = paragraph._p.pPr
        numbered = p_pr is not None and p_pr.numPr is not None
        bullet = "List" in style or numbered or bool(BULLET.match(paragraph.text))
        heading = style.startswith(("Heading", "Title"))
        lines.append(Line(paragraph.text, bullet=bullet, heading=heading))
    return lines


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

def places_for(name, data, text):
    """The places in this resume. Word files use their paragraphs; others the text."""
    if Path(name).suffix.lower() == ".docx":
        return find_places(docx_lines(Document(BytesIO(data))))
    return find_places(text_lines(text))


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


def copy_after(paragraph, text):
    """A new Word paragraph right after this one, with its style, bullet and font."""
    new_p = deepcopy(paragraph._p)  # a full copy of the paragraph's XML
    for child in list(new_p):
        if child.tag != qn("w:pPr"):  # keep only the paragraph settings (pPr):
            new_p.remove(child)  # its style, bullet mark and spacing; drop the words
    paragraph._p.addnext(new_p)  # put the copy right after the original
    new = Paragraph(new_p, paragraph._parent)
    run = new.add_run(text)  # a "run" is a piece of text with one font
    if paragraph.runs and paragraph.runs[0]._r.rPr is not None:
        # rPr = the run's font settings (size, colour); copy the first run's
        run._r.insert(0, deepcopy(paragraph.runs[0]._r.rPr))
    return new


def add_to_docx(data, start, bullets):
    """The bytes of a NEW Word file with the bullets added; formatting is kept."""
    document = Document(BytesIO(data))
    paragraphs = document.paragraphs
    lines = docx_lines(document)
    if start is None:  # "At the end": Word's own bullet style, if the file has it
        for bullet in bullets:
            try:
                document.add_paragraph(bullet, style="List Bullet")
            except KeyError:  # a file without that style: a plain line with a mark
                document.add_paragraph(f"• {bullet}")
    else:
        starts = [i for i in range(len(lines)) if is_place(lines, i)]
        anchor = paragraphs[section_end(lines, start, starts)]
        for bullet in bullets:
            anchor = copy_after(anchor, bullet)  # each new one goes after the last
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def text_to_docx(text):
    """A simple new Word file from plain text (for PDFs): bullets become bullets."""
    document = Document()
    for line in text.splitlines():
        if BULLET.match(line):
            document.add_paragraph(BULLET.sub("", line), style="List Bullet")
        elif line.startswith("#"):
            document.add_heading(line.lstrip("#").strip(), level=1)
        elif line.strip():
            document.add_paragraph(line)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def output_kind(name, pdf_as="docx"):
    """The new file's type: the same as yours, except a PDF becomes pdf_as."""
    kind = Path(name).suffix.lower().lstrip(".")
    return pdf_as if kind == "pdf" else kind


def slug(text):
    """ "Northwind Bank - Senior SRE!" -> "northwind-bank-senior-sre" (max 40)."""
    words = re.findall(r"[a-z0-9]+", text.lower())  # letters and digits only
    return "-".join(words)[:40].strip("-") or "job"


def download_name(job, name, pdf_as="docx"):
    """A new file name for the copy, named after the job: resume-northwind-sre.docx"""
    return f"resume-{slug(job)}.{output_kind(name, pdf_as)}"


def updated_resume(name, data, text, start, bullets, pdf_as="docx"):
    """The bytes of the updated copy. name/data = your file; text = its text."""
    if Path(name).suffix.lower() == ".docx":
        return add_to_docx(data, start, bullets)  # keeps your Word formatting
    new_text = add_to_text(text, start, bullets)
    if output_kind(name, pdf_as) == "docx":  # a PDF, saved as a Word file
        return text_to_docx(new_text)
    # .encode() turns text into bytes, which is what a download needs
    return new_text.encode("utf-8")