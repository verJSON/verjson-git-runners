---
date: 2026-11-18
issue: 197
impact: patch
title: Repin deployment adopter for host observation repository case identity
---

Regenerate the protected container-deployment adopter at
`Verjson/.github@a3a7fe75` so controller and transport compare GitHub
repository identities case-insensitively (ADR 0213 / .github#2225). Enables
re-dispatch of the github-canary dry-run after org-rename display-case failure
on run 44205371156.

Part of #197.
