# Hotfix runbook

1. Fix on main (or a branch + PR for anything non-trivial). Keep the change as small as possible.
2. Push. CI (lint, security rules, tests) must pass; it's a required check.
3. The image workflow builds, smoke-tests, scans (fails on new CRITICAL/HIGH), generates an SBOM, signs and verifies the image.
4. Deploy the new image by its commit tag: ghcr.io/5hayam0hebbi/hireops:<commit sha>.
5. Roll back: redeploy the previous commit's tag. Every image is kept, signed and scanned, so the last good one is always available.

Measured commit-to-signed-image time: 4 minutes (2026-11-26).