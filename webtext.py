# webtext.py - small helpers for showing text on the web pages
def plain(text):
    """Text that Streamlit shows exactly as written.

    Streamlit reads anything between two $ signs as a math formula, so
    "$70,000 - $150,000" would turn into strange symbols. A backslash before
    each $ (written "\\$" in Python) tells Streamlit "just show a dollar sign".
    """
    return text.replace("$", "\\$")