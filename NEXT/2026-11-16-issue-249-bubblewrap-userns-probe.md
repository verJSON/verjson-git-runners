---
date: 2026-11-16
issue: 249
impact: patch
title: Exercise a real Bubblewrap user-namespace in the image contract
---

After provenance and `--version`, the Bubblewrap image contract now runs a
minimal sandbox (`--unshare-user --unshare-pid` … `/bin/true`) and fails closed
with an AppArmor/uid-map diagnostic when that probe is denied. Unit tests cover
one passing fake and one userns denial. The README records the host kernel floor
(`linux-generic-hwe-24.04` / Linux 6.9+ for `PIDFD_SIGNAL_PROCESS_GROUP`). The
behavioral pidfd process-group probe remains deferred under Part of #249.
