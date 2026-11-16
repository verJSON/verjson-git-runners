---
date: 2026-11-16
id: 20261116T060500Z
refs: 208
impact: patch
title: Align generator job egress with runner-isolation
---

Pin `render_egress()` public `ipBlock.except` (including loopback and multicast) and
TCP 443-only ports to the reviewed `deploy/gitlab/runner.json` `runner-isolation`
contract so labeled-job NetworkPolicies cannot widen egress under Kubernetes union
semantics (Part of #208).
