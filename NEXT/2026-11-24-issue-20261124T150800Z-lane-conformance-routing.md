---
date: 2026-11-24
id: 20261124T150800Z
refs: 214
impact: patch
title: Select the trusted lane for the scheduled conformance probe
---

The scheduled Bubblewrap check selects the runner pool named by
`CI_LANE_TRUSTED`. The credential-reference test now reports a forbidden
workflow reference and fails if it cannot complete a search.
