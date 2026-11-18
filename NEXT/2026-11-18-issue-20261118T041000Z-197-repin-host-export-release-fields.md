---
date: 2026-11-18
id: 20261118T041000Z
impact: patch
title: Repin deployment adopter for host-export release fields fix
---
Regenerate the protected runner-deployment caller, review producers, controller,
preflight, transport, receipt schema and contract test at Verjson/.github
`eeafd201e65782e75e446fac03abfa49552b2b64`, which omits `releaseVersion` from the
host-export transport release object and relays a single TransportError line
(.github#2232 / #2231).

Part of #197 / VerJSON/.github#629.
