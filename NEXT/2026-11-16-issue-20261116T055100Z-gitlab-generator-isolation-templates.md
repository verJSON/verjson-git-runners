---
date: 2026-11-16
id: 20261116T055100Z
refs: 208
impact: patch
title: Emit GitLab isolation mounts admission and egress templates
---

Extend `scripts/gitlab_build_config.py` so the credential-free runner template mounts
the reviewed public ConfigMap approval paths, disables service-link admission leakage,
labels restricted jobs, and can render a matching job NetworkPolicy without secrets or
hostPath mounts (Part of #208). Unit and shell tests cover the emission contract; live
Netcup/Nexus activation remains blocked on Verjson/.github#2032.
