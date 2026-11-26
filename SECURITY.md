# Security

HireOps reads resumes, which are personal data. It runs on a local model, so nothing leaves your machine, and every change is checked before it ships.

## What runs automatically

| Check | Tool | When | What happens on a finding |
| --- | --- | --- | --- |
| Dependency updates (SCA) | Dependabot | Weekly | Opens a pull request; reviewed before merge |
| Known vulnerable packages | Dependabot alerts | On every new advisory | Alert, plus a fix PR when a safe version exists |
| Static analysis (SAST) | CodeQL | Every push + weekly | Alert in the Security tab |
| Python security rules (SAST) | Ruff "S" rules (Bandit) | Every push | CI fails |
| Container image scan | Trivy | Every image build | Build fails |

## Reporting a problem

Please open a private security advisory: Security tab → Advisories → Report a vulnerability. Don't open a public issue.