---
date: 2026-11-16
issue: 247
impact: patch
title: Regenerate container-candidate caller for draft deferral
---

Close the remaining draft-capacity gap for issue #247 by regenerating the
adopter `container-candidate` caller, validator twin, destination helper, and
contract test at `19b94586a564c0276e967cf2fd8633bc0f02a53f` (ADR 0261 /
`.github#1944`). Local amd64 image builds were already draft-deferred in #253;
this pin adds `pull_request.types` (without `edited`), concurrency, and
`!github.event.pull_request.draft` on validate so multi-arch candidate work
stays fail-closed on drafts until `ready_for_review`.
