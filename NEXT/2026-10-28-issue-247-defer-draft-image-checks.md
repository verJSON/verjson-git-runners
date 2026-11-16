---
date: 2026-10-28
issue: 247
impact: patch
title: Defer draft pull request image checks
---

Defer expensive draft-PR image work until a pull request is ready. Local amd64
image builds already skip drafts (#253). Regenerate the adopter
`container-candidate` and `container-release` callers, shared helpers, and
contract tests at `19b94586a564c0276e967cf2fd8633bc0f02a53f` (ADR 0261 /
`.github#1944`) so multi-arch validate stays fail-closed on drafts until
`ready_for_review`, and the containers family keeps one shared pin.
