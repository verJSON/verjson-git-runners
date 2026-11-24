---
date: 2026-11-24
id: 20261124T150000Z
refs: 208
impact: patch
title: Fail the GitLab runner configuration test on forbidden settings
---

The shell isolation check now exits with an error when the generated runner
configuration contains a forbidden volume, socket or registry credential setting.
