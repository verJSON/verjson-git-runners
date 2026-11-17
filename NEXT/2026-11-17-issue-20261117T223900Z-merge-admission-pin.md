---
date: 2026-11-17
id: 20261117T223900Z
impact: patch
title: Register merge-admission in hub caller pin inventory
---

Name the ADR 0260 merge-admission producer SHA in `tests/contract_pins.json` and
the hub-caller family map so shell-tests fail closed on drift instead of on an
unregistered callee after landing the generated caller.

Part of verJSON/.github#1945 / verJSON/verjson-git-runners#267.
