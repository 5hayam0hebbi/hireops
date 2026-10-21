# test_matcher.py - automatic checks for the parts of JD Decoder that use plain rules
from bullets import looks_like_bullet, unsupported_numbers
from edits import (
    Removal,
    dropped_names,
    new_names,
    real_removals,
    rewrite_is_useful,
)
from evidence import verified
from extract import RedFlag, quoted_flags
from matcher import MatchResult, match, mentions


def test_whole_words_only():
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
    assert not verified(
        "Managed Terraform for 50 teams", "Built monitoring with Dynatrace"
    )


def test_empty_quote_is_rejected():
    assert not verified("   ", "Built monitoring with Dynatrace")


def test_core_words_on_one_line():
    assert mentions("Built monitoring with Dynatrace and Splunk", "Monitoring Tools")
    assert mentions(
        "Led cross-functional teams of 40", "Cross Functional Team Management"
    )


def test_core_words_must_share_a_line():
    assert not mentions(
        "Led teams\nWorked cross-border", "Cross Functional Team Management"
    )


def test_job_title_is_not_a_bullet():
    resume = "Director, Production Support\n- Ran 24x7 operations"
    assert not looks_like_bullet("Director, Production Support", resume)
    assert looks_like_bullet(
        "Led 24x7 production support for online banking across two data centres", resume
    )


def test_red_flag_needs_words_from_the_posting():
    posting = "On call 24x7 with no team. Salary not disclosed."
    flags = [
        RedFlag(concern="Heavy on-call", quote="On call 24x7 with no team"),
        RedFlag(concern="Vague scope", quote="responsibilities may change"),
    ]
    kept = quoted_flags(flags, posting)
    assert [f.concern for f in kept] == ["Heavy on-call"]


def test_rewrite_must_change_the_line_and_name_the_skill():
    old = "Ran release planning with 6 product teams"
    assert rewrite_is_useful(
        old, "Ran SDLC release planning with 6 product teams", "SDLC"
    )
    assert not rewrite_is_useful(old, old, "SDLC")  # nothing changed
    assert not rewrite_is_useful(old, "Ran planning with product teams", "SDLC")


def test_removals_need_a_real_line():
    lines = ["Led a team of 25 engineers", "Owned disaster recovery exercises"]
    removals = [Removal(line=2, reason="less relevant"), Removal(line=9, reason="x")]
    assert [r.line for r in real_removals(removals, lines)] == [2]


def test_new_tool_names_are_flagged():
    resume = "Built monitoring with Dynatrace"
    new = "Built SDLC monitoring with Dynatrace and Grafana"
    assert new_names(new, resume, "SDLC") == {"Grafana"}


def test_dropped_facts_are_noted():
    old = "Moved workloads to Azure and Docker containers"
    new = "Moved workloads to Azure as part of the SDLC"
    assert dropped_names(old, new) == {"Docker"}
