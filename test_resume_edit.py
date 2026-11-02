# test_resume_edit.py - checks for adding bullets to a copy of a resume
import resume_edit as edit

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