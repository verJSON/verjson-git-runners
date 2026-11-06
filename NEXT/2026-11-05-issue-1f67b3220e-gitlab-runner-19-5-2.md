---
date: 2026-11-05
id: 1f67b3220e
impact: patch
title: Run the GitLab runner canary on GitLab Runner 19.5.2
---

The canary manager Deployment now pins the GitLab Runner 19.5.2 manager image index
`sha256:80015710…`, copied into Nexus with its digest unchanged. It previously pinned 18.3.1.
`deploy/gitlab/README.md` now checks each version-specific claim against the v19.5.2
source. These claims cover the seccomp merge patch, helper `HOME` and job-scoped pull
Secret ordering. A new live evidence file records two protected-main canary jobs.
The 18.3.1 synthetic proof is kept as the only record of the raw-variable and
service-account negative controls, which were not repeated on 19.5.2.
