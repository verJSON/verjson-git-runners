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
# Fail-closed userns opt-in + documented skip when nested CI denies the sandbox.
grep -F 'VERJSON_GITLAB_BUILD_IMAGE_REQUIRE_USERNS' "${script}" >/dev/null
grep -F 'sandbox skipped' "${script}" >/dev/null

# Forbid live-host / privileged surfaces on non-comment lines so comments that
# document "never --privileged" / Netcup exclusion do not self-fail the contract.
# Under set -e, `! grep` is inert; use an explicit fail-closed branch instead.
non_comments="$(grep -Ev '^[[:space:]]*(#|$)' "${script}")"
if printf '%s\n' "${non_comments}" | grep -E 'nexus\.|netcup|privileged[[:space:]]*=[[:space:]]*true|--privileged' >/dev/null; then
  printf 'forbidden live-host or privileged surface in %s\n' "${script}" >&2
  exit 1
fi

printf 'GitLab build-image isolation contract (static) passed\n'
