# test_app.py - checks the web pages work, in a pretend browser (no AI, no internet)
from streamlit.testing.v1 import AppTest

JOB = "Senior SRE. You will run Kubernetes on Azure with Terraform and Python."
WAIT = 30  # seconds a page may take to run; GitHub's computers can be slow


def test_home_page_loads():
    page = AppTest.from_file("app.py").run(timeout=WAIT)
    assert not page.exception  # the page ran without an error
    assert page.title[0].value == "HireOps"


def test_decode_with_rules_only():
    page = AppTest.from_file("pages/1_JD_Decoder.py").run(timeout=WAIT)
    page.text_area[0].input(JOB)  # type the job into the text box
    page.toggle[0].set_value(False)  # AI off: rules only
    page.button[0].click().run(timeout=WAIT)  # click Decode; the page runs again
    assert not page.exception
    shown = " ".join(item.value for item in page.markdown)
    assert "Kubernetes" in shown and "rules only" in shown
