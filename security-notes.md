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

(Filled in on Fri Dec 4.)
