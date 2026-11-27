# test_resume_edit.py - checks for adding bullets to a copy of a resume
from io import BytesIO

from docx import Document

import resume_edit as edit
from resume_files import read_resume

RESUME = """# Alex Rivera

EXPERIENCE

Director, SRE | Northwind Bank | 2019 - 2026
- Led a team of 25 engineers
- Ran incident management for 300+ apps

Senior Manager | Northwind Bank | 2012 - 2019
* Owned disaster recovery exercises

SKILLS
Python, Linux, Azure
"""

NEW = "Cut paging noise by grouping alerts into incidents"


def test_places_are_titles_with_bullets():
    places = edit.find_places(edit.text_lines(RESUME))
    labels = [place.label for place in places]
    # The name, EXPERIENCE and SKILLS have no bullets under them, so they aren't offered
    assert labels == [
        "Director, SRE | Northwind Bank | 2019 - 2026",
        "Senior Manager | Northwind Bank | 2012 - 2019",
        "At the end of the resume",
    ]


def test_a_short_line_above_bullets_is_a_place():
    text = "Alex\nDirector, Site Reliability Engineering\n- Led 25 engineers\n"
    places = edit.find_places(edit.text_lines(text))
    assert places[0].label == "Director, Site Reliability Engineering"


def test_bullets_go_at_the_end_of_the_chosen_section():
    places = edit.find_places(edit.text_lines(RESUME))
    new = edit.add_to_text(RESUME, places[0].start, [NEW])
    lines = new.splitlines()
    # Right after the section's last bullet, with the same "- " mark
    assert lines[lines.index("- Ran incident management for 300+ apps") + 1] == "- " + NEW


def test_the_bullet_mark_of_the_section_is_reused():
    places = edit.find_places(edit.text_lines(RESUME))
    new = edit.add_to_text(RESUME, places[1].start, [NEW])
    assert "* Owned disaster recovery exercises\n* " + NEW in new


def test_at_the_end():
    new = edit.add_to_text(RESUME, None, [NEW, "Second one"])
    assert new.endswith("- " + NEW + "\n- Second one\n")


def test_the_source_line_picks_the_section():
    places = edit.find_places(edit.text_lines(RESUME))
    assert edit.suggested(places, "Owned disaster recovery exercises") == 1
    assert edit.suggested(places, "a line that isn't there") == 0

def test_a_bullet_is_never_added_twice():
    new = edit.add_to_text(RESUME, None, ["Led a team of 25 engineers", NEW])
    assert new.count("Led a team of 25 engineers") == 1
    assert NEW in new


def word_resume():
    """A small Word resume made in memory, with real Word bullets."""
    document = Document()
    document.add_heading("Alex Rivera", level=1)
    document.add_paragraph("Director, SRE | Northwind Bank | 2019 - 2026")
    document.add_paragraph("Led a team of 25 engineers", style="List Bullet")
    last = document.add_paragraph("Ran incident management", style="List Bullet")
    last.runs[0].bold = True  # a font setting the new bullets must copy
    document.add_heading("Skills", level=1)
    document.add_paragraph("Python, Linux, Azure")
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_word_places():
    data = word_resume()
    places = edit.places_for("resume.docx", data, "")
    assert places[0].label == "Director, SRE | Northwind Bank | 2019 - 2026"
    assert places[0].lines == ["Led a team of 25 engineers", "Ran incident management"]


def test_word_bullets_keep_the_style():
    data = word_resume()
    places = edit.places_for("resume.docx", data, "")
    new = edit.add_to_docx(data, places[0].start, [NEW])
    paragraphs = Document(BytesIO(new)).paragraphs
    texts = [p.text for p in paragraphs]
    added = paragraphs[texts.index(NEW)]
    assert texts.index(NEW) == texts.index("Ran incident management") + 1
    assert added.style.name == "List Bullet"
    assert added.runs[0].bold  # the font of the bullet above was copied
    # The original file's bytes are untouched: we only made a new copy
    assert NEW not in read_resume("resume.docx", data)


def test_pdf_becomes_a_word_or_markdown_file():
    text = "Director, SRE\n- Led a team of 25 engineers"
    as_word = edit.updated_resume("cv.pdf", b"", text, 0, [NEW])
    assert NEW in read_resume("new.docx", as_word)
    as_md = edit.updated_resume("cv.pdf", b"", text, 0, [NEW], pdf_as="md")
    assert as_md.decode().endswith("- " + NEW + "\n")


def test_download_name_is_named_after_the_job():
    assert edit.download_name("Northwind SRE", "My Resume.docx") == (
        "resume-northwind-sre.docx"
    )
    assert edit.download_name("Senior SRE!", "cv.pdf", pdf_as="md") == (
        "resume-senior-sre.md"
    )
    assert edit.download_name("", "cv.txt") == "resume-job.txt"