# test_real_jobs.py - regression tests from two real HireOps runs (Oct 28, 2026)
# Each test is a mistake HireOps made on a real job. If a future change brings the
# mistake back, the test fails. None of these call the AI: the AI's answers are faked.
import decoder
import evidence
from bullets import bullet_warnings
from evidence import find_by_meaning, named_tools, proves
from extract import (
    JobInsights,
    RedFlag,
    Requirement,
    apply_text_rules,
    is_vague,
    quoted_flags,
    said_not_needed,
)
from matcher import mentions

# Short lines in the style of Shaya's resume (each line is one resume bullet)
RESUME = """- Scaled self-healing automation across the portfolio, resolving ~90% of known issues without human intervention.
- Converted 200 manual runbooks into automated remediation, cutting after-hours effort by 35% and reducing P2-P4 incident volume.
- Integrated Dynatrace, Splunk and ELK into one alerting flow, cutting mean time to detect by 55% and MTTR by 40%.
- Remediated ~150 inherited audit findings by ranking them by risk and holding vendors to delivery dates.
- Owned an $8M annual budget and 10 vendor relationships, including managed-service and offshore support providers.
- Raised availability across critical systems to 99.9% with SLOs, error budgets and readiness gates."""

# Ashby-style posting: it names its stack, then says you don't need it
ASHBY_JOB = """You'll manage three to five engineers and hire three to five more.

Why you shouldn't apply: you don't enjoy coding or don't stay up-to-date on technology.

I’m sharing our tech stack with the caveat that we don’t require previous experience in it: TypeScript, React, GraphQL API, Node.js, Postgres, Redis."""
# (curly apostrophes on purpose: the real posting uses them, and they broke a rule)


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
    monkeypatch.setattr(decoder, "suggest_bullets", lambda job, resume, focus: [])
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


# --- Ashby, second run (Oct 28): vague names and a wrong "not required" ---------------


def test_umbrella_names_are_dropped():
    assert is_vague("Technical Skills")
    assert is_vague("Leadership Experience")
    assert not is_vague("Stakeholder Communication")
    assert not is_vague("Coaching Engineers")


def test_ai_cannot_mark_coding_not_required_without_proof():
    # The AI said "Hands-on Coding" wasn't needed; the posting never says that
    ai_said = [
        Requirement(name="Technical Skills", importance="must-have"),
        Requirement(name="Hands-on Coding", importance="not required"),
        Requirement(name="Redis", importance="not required"),
    ]
    fixed = apply_text_rules(ai_said, ASHBY_JOB)
    assert [(r.name, r.importance) for r in fixed] == [
        ("Hands-on Coding", "must-have"),  # no proof, so back to must-have
        ("Redis", "not required"),  # the posting really says so
    ]


def test_warning_quotes_the_real_word():
    bullet = (
        "Improved reliability standards and automation for critical systems, raising "
        "availability across critical systems to 99.9% with SLOs."
    )
    warnings = bullet_warnings(bullet, RESUME, gaps=[])
    assert 'says "automation", but your resume line doesn\'t' in warnings


def test_bullets_are_aimed_at_the_must_haves(monkeypatch):
    import bullets

    prompts = []  # the fake AI saves each prompt here, so we can read it

    def fake_ask(prompt, shape, temperature=0):
        prompts.append(prompt)
        idea = bullets.BulletIdea(
            text="Converted 200 manual runbooks into automated remediation for the team",
            line=2,
        )
        return bullets.Bullets(bullets=[idea])

    monkeypatch.setattr(bullets, "ask", fake_ask)
    bullets.suggest_bullets("any job", RESUME, focus=["coaching engineers", "hiring"])
    assert "coaching engineers, hiring" in prompts[0]


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


# --- Modern Niagara and BMO (Oct 29): labels in names, made-up requirements ------------

NIAGARA_JOB = """Reporting to the VP, the Director provides both strategic direction and
hands-on technical leadership.

Deep, current, hands-on experience administering Microsoft Azure infrastructure.
Strong working knowledge of enterprise networking, including routing and firewalls."""

BMO_JOB = """Experience using Python for custom evaluations and SQL or LogQL/PromQL for
querying telemetry, logs, and metrics data.

Broader work or accountabilities may be assigned as needed.

Take measured risks while protecting the bank by applying our Risk Management
Framework, in line with our Risk Culture and within our approved Risk Appetite."""


def test_labels_are_removed_from_names():
    ai_said = [
        Requirement(name="Microsoft Azure administration experience (must-have)", importance="must-have"),
        Requirement(name="Enterprise networking knowledge (not required)", importance="not required"),
    ]
    fixed = apply_text_rules(ai_said, NIAGARA_JOB)
    assert [(r.name, r.importance) for r in fixed] == [
        ("Microsoft Azure administration experience", "must-have"),
        ("Enterprise networking knowledge", "must-have"),  # no proof it's not needed
    ]


def test_requirement_the_posting_never_mentions_is_dropped():
    # "hands-on technical leadership" is in the posting; "coding" is not
    ai_said = [Requirement(name="hands-on coding", importance="must-have")]
    assert apply_text_rules(ai_said, NIAGARA_JOB) == []


def test_long_names_match_the_resume():
    resume = "Ran COB's internet-facing component on Microsoft Azure with Splunk"
    assert mentions(resume, "Microsoft Azure administration experience")
    assert mentions("Wrote SQL reports", "SQL or LogQL/PromQL querying experience")
    assert mentions("Python (FastAPI, pytest)", "Python programming skills")


def test_boilerplate_is_not_a_red_flag():
    flags = [
        RedFlag(concern="Unclear scope", quote="Broader work or accountabilities may be assigned as needed."),
        RedFlag(concern="Risk", quote="applying our Risk Management Framework"),
    ]
    assert quoted_flags(flags, BMO_JOB) == []


# --- Bullets that borrow claims from the job (Ashby, BMO) -------------------------------

SKILLS_LINE = "- AI: Local LLMs (Ollama / Llama 3.2), Claude API, GPT-4, Pydantic structured outputs, Make.com"
LAB_LINE = "- self-healing-lab: Prometheus alerts and Alertmanager trigger a Python remediator that restarts the failed container; Grafana shows each recovery"


def test_ashby_bullet_borrowed_talent_acquisition():
    bullet = (
        "Developed and maintained AI-powered tooling for Talent Acquisition software, "
        "utilizing Claude API, GPT-4, Pydantic structured outputs, and Make.com."
    )
    job = "We build Talent Acquisition software with AI-powered tooling."
    warnings = bullet_warnings(bullet, RESUME + "\n" + SKILLS_LINE, [], line=SKILLS_LINE, job_text=job)
    assert any('"talent"' in w and '"acquisition"' in w for w in warnings)


def test_bmo_bullet_borrowed_ai_model_performance():
    bullet = (
        "Built a Docker Compose self-healing lab with Prometheus, Alertmanager, and "
        "Grafana to monitor and troubleshoot AI model performance."
    )
    job = "Track model drift, latency spikes and error rates across production pipelines."
    warnings = bullet_warnings(bullet, RESUME + "\n" + LAB_LINE, [], line=LAB_LINE, job_text=job)
    assert any('"model"' in w for w in warnings)


def fake_ideas(*ideas):
    """A fake ask() that answers with these (text, line number) bullet ideas."""
    import bullets

    def fake_ask(prompt, shape, temperature=0):
        return bullets.Bullets(bullets=[bullets.BulletIdea(text=t, line=n) for t, n in ideas])

    return fake_ask


def test_bullet_unlike_its_source_line_is_dropped(monkeypatch):
    import bullets

    monkeypatch.setattr(bullets, "ask", fake_ideas(
        # line 4 is the audit findings line: this bullet shares almost nothing with it
        ("Created and led training sessions on observability tools to improve monitoring", 4),
        # line 99 doesn't exist
        ("Converted 200 manual runbooks into automated remediation for the whole team", 99),
        # a real one: line 2 is the runbooks line
        ("Converted 200 manual runbooks into automated remediation, cutting after-hours effort by 35%", 2),
    ))
    found = bullets.suggest_bullets("any job", RESUME)
    assert [s.text[:30] for s in found] == ["Converted 200 manual runbooks "]
    assert found[0].source.startswith("Converted 200 manual runbooks")


# --- Token counts --------------------------------------------------------------------


class FakeResponse:
    """Looks like an Ollama answer: JSON text plus the counts Ollama reports."""

    def __init__(self, content, prompt_tokens, output_tokens, nanoseconds):
        self.message = type("Message", (), {"content": content})()
        self.done_reason = "stop"
        self.prompt_eval_count = prompt_tokens
        self.eval_count = output_tokens
        self.total_duration = nanoseconds


def test_every_ai_call_records_its_tokens(monkeypatch):
    import ai

    monkeypatch.setattr(ai, "usage_log", [])  # an empty log just for this test
    answer = FakeResponse('{"bullets": []}', 1200, 80, 2_500_000_000)
    monkeypatch.setattr(ai.client, "chat", lambda **kwargs: answer)
    import bullets

    ai.ask("prompt", bullets.Bullets)
    assert ai.usage_log == [ai.Usage("Bullets", 1200, 80, 2.5, 1)]


def test_decode_adds_up_this_runs_tokens(monkeypatch):
    import ai

    def fake_extract(job_text):
        # pretend two AI calls happened while reading the job
        ai.usage_log.append(ai.Usage("JobInsights", 3000, 400, 20.0, 1))
        ai.usage_log.append(ai.Usage("JobInsights", 3000, 350, 18.5, 2))
        return JobInsights(role_title="SRE", seniority="senior", requirements=[], red_flags=[])

    monkeypatch.setattr(ai, "usage_log", [ai.Usage("old run", 9, 9, 9.0, 1)])
    monkeypatch.setattr(decoder, "extract", fake_extract)
    decoded = decoder.decode("any job")  # no resume: stops after reading the job
    assert decoded.tokens() == {
        "calls": 2,
        "prompt_tokens": 6000,
        "output_tokens": 750,
        "seconds": 38.5,
    }
