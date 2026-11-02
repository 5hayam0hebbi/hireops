# test_webtext.py - checks for the web page text helpers
from webtext import plain


def test_dollar_signs_are_shown_as_written():
    assert plain("$70,000 - $150,000") == "\\$70,000 - \\$150,000"


def test_text_without_dollars_is_unchanged():
    assert plain("Owned an 8M budget") == "Owned an 8M budget"