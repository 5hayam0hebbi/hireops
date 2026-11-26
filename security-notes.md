# Security notes

A running log of what the security scans found and what was done about it.
Newest entry at the bottom of each section.

## Trivy image scan (CRITICAL and HIGH, fixable only)

| Date | CRITICAL | HIGH | Notes |
| --- | --- | --- | --- |
| 2026-11-26 | 0 | 1 | First scan. Finding below. |
| 2026-11-26 | 0 | 0 | After patching the base image (commit f20289f). Clean. |

### Findings

| Date found | Package | CVE | Severity | Installed | Fixed in | What it is | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-11-26 | libzstd1 (Debian package in the python:3.12-slim base image) | CVE-2026-124851 | HIGH | 1.5.7+dfsg-1 | 1.5.7+dfsg-1+deb13u1 | zstd information disclosure via an uninitialized buffer | Fixed 2026-11-26: added apt-get upgrade to the Dockerfile (commit f20289f); re-scan shows 0 |

Note: in Trivy's table, Status "fixed" means a fixed version has been released, not that it's fixed in this image yet.

## Dependabot

| Date | Pull request | What it updates | Decision | Why |
| --- | --- | --- | --- | --- |
| 2026-11-26 | #10 | narwhals 2.28.0 → 2.29.0 (pip) | Merged | Minor version bump, one-line change, CI green |

## SAST (CodeQL and Ruff security rules)

| Date | Tool | Findings | Notes |
| --- | --- | --- | --- |
| 2026-11-26 | CodeQL (python + actions) | 3 Medium, missing workflow permissions | First scan, default setup |
| 2026-11-26 | Ruff S rules | 204 S101, 0 after tuning | All S101 are assert in test files (false positives) |
| 2026-11-26 | CodeQL (python + actions) | 3 Medium, all fixed | Missing workflow permissions; added contents: read (least privilege) |

## Interview answers

### 1. "How have you handled vulnerable dependencies?"

I set up Dependabot on my HireOps project to watch three things: the Python packages in requirements.txt, the GitHub Actions the pipelines use, and the Docker base image. It checks weekly and opens a pull request when a newer or safer version is out. I capped it at five open pull requests at a time, so the team gets a queue it can actually review instead of a flood.

I review each pull request the way I'd review a contractor's change: read the release notes for anything breaking or removed, check that the diff is only the version change, and make sure CI (lint and the full test suite) is green before merging. The first one I merged was narwhals 2.28.0 to 2.29.0: a minor bump, a one-line change, CI green. If CI fails, I hold the pull request with a comment explaining why instead of merging.

A real example of why this matters: while setting up image scanning, the scanner's own GitHub Action had re-tagged every version after a supply-chain attack. Pinned versions in pipelines need watching too, and Dependabot now does that for the actions as well.

### 2. "How do you patch container images?"

Every image build now runs a Trivy scan for CRITICAL and HIGH vulnerabilities that have a fix available. The first scan found one HIGH finding, CVE-2026-124851 in libzstd1, a Linux package inside the python:3.12-slim base image, not in my code. I fixed it at build time by adding one line to the Dockerfile that installs the latest Debian security updates, rebuilt, and the re-scan showed zero. Before: 0 critical, 1 high. After: 0 and 0, the same day.

Once the image was clean, I switched the scan from report-only to enforcing: any new CRITICAL or HIGH finding now fails the build, so a vulnerable image can't be published. That mirrors the order I'd use on a real portfolio: measure first, fix the backlog, then turn on the gate so it stays fixed.

### 3. "How do you build SAST into delivery?"

Two layers. CodeQL runs on every push and weekly, covering both the Python code and the pipeline files. Its first scan found three medium issues, all the same thing: workflows without explicit permissions, so their tokens could have had more access than needed. I added read-only permissions to each one (least privilege), and the alerts closed on the next scan.

The second layer is Ruff's security rules (from the Bandit scanner), enforced in CI, so new risky code fails the build before it merges. The first run flagged 204 findings, but every one was the assert rule in test files, where assert is exactly what tests should use. That's a false positive, so I turned that one rule off for test files only. Real code is still fully covered, and the remaining result was zero. Tuning out false positives matters, because developers stop trusting a scanner that cries wolf.

This is the same approach I ran at RBC as a team lead and senior manager: SonarQube and Checkmarx scans were a mandatory check before every release. I generated the reports and worked the findings through with the development teams until they were resolved. The difference now is that I've built the whole pipeline myself, end to end.
