---
date: 2026-11-27
id: 20261127T154720Z
impact: patch
title: Surface safe runner evidence adapter failures
---

Report fixed diagnostics when the deployment evidence adapter cannot read
GitHub release metadata, download the release manifest, or resolve the Git
checkout identity. Public dry-run logs can distinguish these failure stages
and report valid HTTP error statuses without exposing URLs or provider text.
The shell test job now runs the offline adapter suite.

Part of [#197](https://github.com/verJSON/verjson-git-runners/issues/197).
The [protected dry run](https://github.com/verJSON/verjson-git-runners/actions/runs/46026637316)
reported a generic adapter failure, so its underlying cause remains unidentified.
