---
date: 2026-11-27
id: 20261127T144713Z
impact: patch
title: Preserve structured doctl status in deployment diagnostics
---

Regenerate the protected deployment adopter at
`9026a267b3bd5a22d97b6ed775bd811ebb24de38`. Failed host-evidence probes now
distinguish HTTP 401 from HTTP 403 using the structured `doctl` response,
including when the response has no request ID.

Part of [#197](https://github.com/verJSON/verjson-git-runners/issues/197).
[Canonical policy fix](https://github.com/verJSON/.github/pull/2299)
