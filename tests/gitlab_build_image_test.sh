#!/usr/bin/env bash
# Opt-in local/GHCR image behavior proof. Pull/provenance validation is a separate receipt.
# Synthetic only: do not point this at Netcup/Nexus live digests or claim live WEB acceptance.
set -euo pipefail
image="${1:?usage: gitlab_build_image_test.sh ghcr.io/verjson/gha-runner@sha256:<digest>}"
[[ "$image" =~ ^ghcr\.io/verjson/gha-runner(-node|-python|-go|-rust|-pwsh)?@sha256:[a-f0-9]{64}$ ]] || exit 2

require_userns="${VERJSON_GITLAB_BUILD_IMAGE_REQUIRE_USERNS:-0}"

# Shared in-container checks: identity, no Docker socket, no privilege path, Bubblewrap present.
# User-namespace probe is best-effort here under Docker's default seccomp (often denies unshare).
restricted_script='
  set -euo pipefail
  test "$(id -u)" = 1001
  test ! -e /var/run/docker.sock
  test ! -S /var/run/docker.sock
  test -w /tmp
  test -n "$(command -v git)"
  test -n "$(command -v bash)"
  if sudo -n true 2>/dev/null; then echo "sudo escalation unexpectedly succeeded" >&2; exit 1; fi
  if ps -eo args | grep -E "[R]unner.Listener|[/]entrypoint.sh"; then exit 1; fi
  test -x /usr/bin/bwrap
  test -f /usr/bin/bwrap
  if test -L /usr/bin/bwrap; then echo "/usr/bin/bwrap must not be a symlink" >&2; exit 1; fi
  userns_err="$(mktemp)"
  if /usr/bin/bwrap --unshare-user --unshare-pid --die-with-parent --ro-bind / / --proc /proc -- /bin/true 2>"${userns_err}"; then
    printf "userns=ok\n"
  else
    printf "userns=denied\n"
    cat "${userns_err}" >&2 || true
  fi
  rm -f "${userns_err}"
  printf "GitLab shell contract passed: uid=%s; sudo denied; no docker.sock; bwrap present; no GitHub listener\n" "$(id -u)"
'

run_restricted() {
  docker run --rm --pull never --network none --user 1001:1001 \
    --cap-drop ALL --security-opt no-new-privileges --memory 1g --cpus 1 \
    --entrypoint /bin/bash "$image" -euc "${restricted_script}"
}

restricted_out="$(run_restricted)"
printf '%s\n' "${restricted_out}"

if printf '%s\n' "${restricted_out}" | grep -q '^userns=ok$'; then
  printf 'GitLab Bubblewrap user-namespace sandbox passed under restricted docker opts\n'
  exit 0
fi

# Nested Docker default seccomp commonly denies unshare (same class as RuntimeDefault).
# Retry with seccomp=unconfined only for the sandbox probe: still non-root, cap-drop ALL,
# no-new-privileges, no docker.sock, never --privileged.
userns_script='
  set -euo pipefail
  test "$(id -u)" = 1001
  test ! -S /var/run/docker.sock
  test -x /usr/bin/bwrap
  /usr/bin/bwrap --unshare-user --unshare-pid --die-with-parent --ro-bind / / --proc /proc -- /bin/true
  printf "GitLab Bubblewrap user-namespace sandbox passed (seccomp=unconfined synthetic probe)\n"
'

if docker run --rm --pull never --network none --user 1001:1001 \
  --cap-drop ALL --security-opt no-new-privileges --security-opt seccomp=unconfined \
  --memory 1g --cpus 1 \
  --entrypoint /bin/bash "$image" -euc "${userns_script}"; then
  exit 0
fi

msg='GitLab Bubblewrap user-namespace sandbox skipped: nested CI/runtime denied userns (not a live GitLab WEB acceptance substitute). Set VERJSON_GITLAB_BUILD_IMAGE_REQUIRE_USERNS=1 to fail closed.'
if [[ "${require_userns}" == "1" ]]; then
  printf '%s\n' "${msg}" >&2
  exit 1
fi
printf '%s\n' "${msg}"
