---
date: 2026-11-16
id: 20261116T150558Z
refs: 208
impact: patch
title: Synthetic GitLab build-image isolation probe
---

Extend the local/GHCR GitLab build-image probe to require `/usr/bin/bwrap`, exercise a
real Bubblewrap user-namespace sandbox (with a documented skip when nested CI denies
userns), and keep the no-`docker.sock` / no-privilege path. The credential-free
generator now emits `allowed_docker_credential_helpers = []` (Part of #208). Live
Netcup/Nexus WEB acceptance remains blocked on Verjson/.github#2032.
