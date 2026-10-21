# test_matcher.py - automatic checks for the parts of JD Decoder that use plain rules
from bullets import unsupported_numbers
from evidence import verified
from matcher import MatchResult, match, mentions


def test_whole_words_only():
    # "slow" contains the letters "slo", but it isn't the skill SLO
    assert not mentions("Users say the pages are slow", "SLO")


def test_plural_matches():
    assert mentions("Define SLOs and error budgets", "SLO")


def test_any_letter_case():
    assert mentions("writes python scripts", "Python")


def test_special_characters():
    assert mentions("Build CI/CD pipelines", "CI/CD")


def test_alias_counts_as_the_skill():
    assert mentions("Led a team of 25 engineers", "Leadership")


def test_score_and_missing():
    result = MatchResult(
        wanted=["Python", "Azure", "Kubernetes", "Linux"], have=["Python", "Linux"]
    )
    assert result.score() == 50
    assert result.missing() == ["Azure", "Kubernetes"]


def test_no_wanted_skills_scores_zero():
    assert MatchResult(wanted=[], have=[]).score() == 0


def test_sample_files():
    # The sample job and resume in the repo should always give the same answer
    with open("samples/job.txt") as f:
        job_text = f.read()
    with open("samples/resume.md") as f:
        resume_text = f.read()
    result = match(job_text, resume_text, ["Python", "Kubernetes", "Leadership"])
    assert result.have == ["Python", "Leadership"]
    assert result.missing() == ["Kubernetes"]


def test_numbers_from_the_resume_are_fine():
    assert (
        unsupported_numbers("Led 25 engineers", "Led a team of 25 engineers") == set()
    )


def test_invented_number_is_caught():
    assert unsupported_numbers(
        "Cut costs by 40%", "Ran operations for online banking"
    ) == {"40"}

def test_quote_in_resume_is_verified():
    resume = "Built monitoring with Dynatrace"
    assert verified("built  MONITORING with dynatrace", resume)


def test_invented_quote_is_rejected():
    assert not verified("Managed Terraform for 50 teams", "Built monitoring with Dynatrace")


def test_empty_quote_is_rejected():
    assert not verified("   ", "Built monitoring with Dynatrace")