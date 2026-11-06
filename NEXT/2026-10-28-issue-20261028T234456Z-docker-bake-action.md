---
date: 2026-10-28
id: 20261028T234456Z
impact: patch
title: Update the Docker Bake action
---

Update Docker Bake to v7.5.0 in the runner image verification workflow. The existing PR path checks amd64; the scheduled arm64 path requires separate verification.
