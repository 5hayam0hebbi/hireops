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
| 2026-11-26 | #11 | streamlit 1.66.1 → 1.67.0 (pip, minor) | Merged | Minor update; release notes reviewed; one-line change; CI green |

## SAST (CodeQL and Ruff security rules)

| Date | Tool | Findings | Notes |
| --- | --- | --- | --- |
| 2026-11-26 | CodeQL (python + actions) | 3 Medium, missing workflow permissions | First scan, default setup |
| 2026-11-26 | Ruff S rules | 204 S101, 0 after tuning | All S101 are assert in test files (false positives) |
| 2026-11-26 | CodeQL (python + actions) | 3 Medium, all fixed | Missing workflow permissions; added contents: read (least privilege) |

## SBOM and signing

| Date | What | Result |
| --- | --- | --- |
| 2026-11-26 | SBOM (SPDX) generated for every image, kept 90 days | 140 packages; libzstd1 confirmed at the patched version |
| 2026-11-26 | Keyless image signing (cosign) + SBOM attestation, verified in the pipeline | Every image on main is signed and carries its SBOM (Rekor log index 4135427551) |
| 2026-11-26 | Fast-track lane: Dependabot patch updates auto-merge after required CI; minor/major still reviewed | Lane tested on #11 (minor): workflow ran, merge correctly skipped for manual review |

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

### 4. "How do you manage SBOMs?"

Every image my pipeline builds gets a software bill of materials in SPDX, a standard format other tools can read. It lists every Linux and Python package inside the image with its exact version. For HireOps that's 140 packages. The SBOM is kept with each build for 90 days, and it's also attached to the signed image as a signed attestation, so the ingredients list travels with the image wherever it's deployed.

The practical value is speed when a new CVE is announced. Instead of rebuilding or guessing, you search the SBOMs for the affected package and version and know within minutes which images are exposed. I tested exactly that: after patching the base image, I searched the SBOM and confirmed libzstd1 was at the fixed version. At portfolio scale, the same idea answers the audit question "show me everything running this library" without a manual hunt.

### 5. "How do you know an image wasn't tampered with?"

I sign every image in the pipeline with cosign, using keyless signing. There's no private key to store or leak: GitHub vouches for the workflow's identity, and the signature is recorded in Sigstore's public transparency log. The pipeline signs the image by its digest, its exact fingerprint, so re-tagging can't swap in a different image.

The pipeline then verifies its own signature as a final step, checking that it was issued to this repository's workflow running on main. If anything doesn't match, the build fails. A deployment step can run the same verification before it pulls an image, so only images built and signed by our own pipeline ever run. The SBOM is attached under the same signature, so the image and its ingredients list are tied together.

### 6. "How fast can your pipeline ship a security fix, and how do you fast-track patches safely?"

I measured it. From commit to a published image that is built, smoke-tested, scanned, SBOM'd, signed and verified, my pipeline takes about 4 minutes. That's comfortably inside a same-day fix target; the slow part in most organizations is approvals and handoffs, not the pipeline. I wrote a short hotfix runbook, and rollback is simple: every image is kept, signed and tagged by commit, so you redeploy the last good one.

For routine patches I built a fast-track lane with the gate still in place. CI is a required check on main. Dependabot patch updates (only the last version number changes) merge automatically, but only after CI passes. Minor and major updates still wait for a human review of release notes, the diff and CI. When two dependency PRs conflicted, I had Dependabot rebase onto main instead of hand-editing. It's the same balance I'd aim for at a bank: let low-risk fixes flow without a meeting, and keep the review where the risk actually is.
