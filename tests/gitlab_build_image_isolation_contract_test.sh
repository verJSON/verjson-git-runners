#!/usr/bin/env bash
# Always-on contract: the opt-in image probe encodes Bubblewrap / no-socket / no-privilege
# isolation checks (synthetic local/GHCR only; not live Netcup/Nexus acceptance).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
script="${root}/tests/gitlab_build_image_test.sh"

grep -F '/usr/bin/bwrap' "${script}" >/dev/null
grep -E -- '--unshare-user' "${script}" >/dev/null
grep -F 'docker.sock' "${script}" >/dev/null
grep -E 'no-new-privileges|allow_privilege_escalation|sudo' "${script}" >/dev/null
grep -E 'USERNS|user namespace|userns' "${script}" >/dev/null
grep -E 'skip|SKIP' "${script}" >/dev/null
! grep -E 'nexus\.|netcup|privileged = true|--privileged' "${script}" >/dev/null

printf 'GitLab build-image isolation contract (static) passed\n'
