---
date: 2026-11-18
id: 20261118T033500Z
impact: patch
title: Repin deployment adopter for release.repository historical source split
---
Regenerate the protected runner-deployment caller, review producers, controller,
preflight, transport, receipt schema and contract test at Verjson/.github
`8150f373dbb2b6e492bc37aeb6bacf6fb3417259`, which binds host-export release.repository to the historical
signed manifest source after the github-runner→git-runners rename (.github#2229).

Part of #197 / VerJSON/.github#629.
