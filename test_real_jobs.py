# test_real_jobs.py - regression tests from two real HireOps runs (Oct 28, 2026)
# Each test is a mistake HireOps made on a real job. If a future change brings the
# mistake back, the test fails. None of these call the AI: the AI's answers are faked.
import decoder
import evidence
from bullets import bullet_warnings
from evidence import find_by_meaning, named_tools, proves
from extract import JobInsights, Requirement, apply_text_rules, said_not_needed

# Short lines in the style of Shaya's resume (each line is one resume bullet)
RESUME = """- Scaled self-healing automation across the portfolio, resolving ~90% of known issues without human intervention.
- Converted 200 manual runbooks into automated remediation, cutting after-hours effort by 35% and reducing P2-P4 incident volume.
- Integrated Dynatrace, Splunk and ELK into one alerting flow, cutting mean time to detect by 55% and MTTR by 40%.
- Remediated ~150 inherited audit findings by ranking them by risk and holding vendors to delivery dates.
- Owned an $8M annual budget and 10 vendor relationships, including managed-service and offshore support providers.
- Raised availability across critical systems to 99.9% with SLOs, error budgets and readiness gates."""

# Ashby-style posting: it names its stack, then says you don't need it
ASHBY_JOB = """You'll manage three to five engineers and hire three to five more.

I'm sharing our tech stack with the caveat that we don't require previous experience in it: TypeScript, React, GraphQL API, Node.js, Postgres, Redis."""


# --- Ashby: the tech stack is "not required" -----------------------------------------


def test_ashby_stack_is_labelled_not_required():
    assert said_not_needed("TypeScript", ASHBY_JOB)
    assert said_not_needed("Postgres", ASHBY_JOB)
    assert not said_not_needed("hiring", ASHBY_JOB)  # a different paragraph


def test_rules_overrule_the_ai_label():
    # The AI wrongly called TypeScript a must-have; the posting's words win
    ai_said = [
        Requirement(name="TypeScript", importance="must-have"),
        Requirement(name="hiring engineers", importance="must-have"),
        Requirement(name="typescript", importance="must-have"),  # a repeat
    ]
    fixed = apply_text_rules(ai_said, ASHBY_JOB)
    assert [(r.name, r.importance) for r in fixed] == [
        ("TypeScript", "not required"),
        ("hiring engineers", "must-have"),
    ]


def test_not_required_skills_are_not_scored():
    insights = JobInsights(
        role_title="Engineering Manager",
        seniority="lead",
        requirements=[
            Requirement(name="coaching engineers", importance="must-have"),
            Requirement(name="TypeScript", importance="not required"),
        ],
        red_flags=[],
    )
    assert insights.skills == ["coaching engineers"]
    assert insights.not_required == ["TypeScript"]


def test_score_breakdown_weights_must_haves(monkeypatch):
    def fake_extract(job_text):
        return JobInsights(
            role_title="Manager, SRE",
            seniority="lead",
            requirements=[
                Requirement(name="SLOs", importance="must-have"),
                Requirement(name="AWS", importance="must-have"),
                Requirement(name="Dynatrace", importance="nice-to-have"),
                Requirement(name="TypeScript", importance="not required"),
            ],
            red_flags=[],
        )

    monkeypatch.setattr(decoder, "extract", fake_extract)
    monkeypatch.setattr(decoder, "find_by_meaning", lambda missing, resume: {})
    monkeypatch.setattr(decoder, "suggest_bullets", lambda job, resume: [])
    decoded = decoder.decode("any job", RESUME)
    assert decoded.breakdown() == {"must": (1, 2), "nice": (1, 1), "not_required": 1}
    assert decoded.weighted_score() == 60  # (2*1 + 1) of (2*2 + 1)
    assert decoded.gaps() == ["AWS"]  # a real gap, not a bullet


# --- Lightspeed: "providers" in a budget line is not AWS/GCP experience ---------------


def test_named_tools_come_from_brackets():
    assert named_tools("Cloud Infrastructure Providers (AWS,GCP)") == ["AWS", "GCP"]
    assert named_tools("TypeScript") == ["TypeScript"]
    assert named_tools("incident management") == []


def test_budget_line_is_not_cloud_provider_proof():
    budget = "Owned an $8M annual budget and 10 vendor relationships, including managed-service and offshore support providers."
    assert not proves("Cloud Infrastructure Providers (AWS,GCP)", budget)
    assert proves("Cloud Infrastructure Providers (AWS,GCP)", "Deployed services on AWS")


def test_meaning_check_drops_the_budget_line(monkeypatch):
    # Fake AI: points AWS/GCP at the budget line (line 5), as it did on Lightspeed
    def fake_ask(prompt, shape):
        return evidence.EvidenceList(
            found=[
                evidence.Evidence(skill="Cloud Infrastructure Providers (AWS,GCP)", line=5),
                evidence.Evidence(skill="high availability", line=6),
            ]
        )

    monkeypatch.setattr(evidence, "ask", fake_ask)
    missing = ["Cloud Infrastructure Providers (AWS,GCP)", "high availability"]
    found = find_by_meaning(missing, RESUME)
    assert "Cloud Infrastructure Providers (AWS,GCP)" not in found
    assert "99.9%" in found["high availability"]  # a real meaning match stays


# --- Bullets that mixed up facts --------------------------------------------------------


def test_ashby_bullet_glued_35_to_self_healing():
    bullet = (
        "Scaled self-healing automation across the portfolio to resolve ~90% of known "
        "issues without human intervention, reducing P2-P4 incident volume by 35%."
    )
    warnings = bullet_warnings(bullet, RESUME, gaps=[])
    assert warnings == [
        "35 comes from a different resume line, not the one this bullet is about"
    ]  # only 35: the 2 and 4 in "P2-P4" are labels, not numbers


def test_lightspeed_bullet_gave_mttd_to_self_healing():
    bullet = (
        "Led a self-healing automation framework across the portfolio, resolving known "
        "issues without human intervention and reducing mean time to detect by 55%."
    )
    warnings = bullet_warnings(bullet, RESUME, gaps=[])
    assert any(w.startswith("55 comes from a different resume line") for w in warnings)


def test_lightspeed_bullet_upgraded_audit_fixes_to_automated():
    bullet = (
        "Automated the remediation of ~150 inherited audit findings, ranking them by "
        "risk and holding vendors to delivery dates."
    )
    warnings = bullet_warnings(bullet, RESUME, gaps=[])
    assert 'says "automated", but your resume line doesn\'t' in warnings


def test_bullet_must_not_name_a_real_gap():
    bullet = "Raised availability across critical AWS systems to 99.9% with SLOs and error budgets."
    warnings = bullet_warnings(bullet, RESUME, gaps=["AWS"])
    assert "names AWS, which your resume doesn't show" in warnings


def test_honest_bullet_has_no_warnings():
    bullet = (
        "Converted 200 manual runbooks into automated remediation, cutting after-hours "
        "effort by 35% and reducing P2-P4 incident volume."
    )
    assert bullet_warnings(bullet, RESUME, gaps=["AWS"]) == []
