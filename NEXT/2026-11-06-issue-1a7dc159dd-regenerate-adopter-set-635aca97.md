---
date: 2026-11-06
id: 1a7dc159dd
impact: patch
title: Regenerate the canonical adopter set at contract 635aca97
---

Regenerate every generated contract artifact this repository carries at `verJSON/.github` main `635aca975b1aa93660138875ba9616b27693476f`, replacing the v4.4.0 pin (`b12cc46b8439d1573fcc32cf595854530361641b`) with byte-exact generator output and the same recorded arguments. The generated gate re-arm caller gains the `guard` job, and `rearm` now runs only when that guard does not report `local_arm=false`, so the repository-local arm yields to the organization arm. The container release contract test now names each failed assertion. The `builderIdentity` pins in `container-candidate.json` and the repository's contract pin tests move to the same SHA.
