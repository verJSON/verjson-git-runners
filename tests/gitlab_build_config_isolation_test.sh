#!/usr/bin/env bash
# Credential-free generator isolation contract: mounts, admission, egress.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

contract="${tmp}/contract.json"
cat >"${contract}" <<'EOF'
{
  "registry": "nexus.example.org",
  "namespace": "gitlab-jobs",
  "architecture": "amd64",
  "build": {
    "source": "ghcr.io/verjson/gha-runner-node@sha256:1111111111111111111111111111111111111111111111111111111111111111",
    "destination": "nexus.example.org/build@sha256:1111111111111111111111111111111111111111111111111111111111111111",
    "version": "19.5.2"
  },
  "manager": {
    "source": "registry.gitlab.com/gitlab-org/gitlab-runner@sha256:2222222222222222222222222222222222222222222222222222222222222222",
    "destination": "nexus.example.org/manager@sha256:2222222222222222222222222222222222222222222222222222222222222222",
    "version": "19.5.2"
  },
  "helper": {
    "source": "registry.gitlab.com/gitlab-org/gitlab-runner/gitlab-runner-helper@sha256:3333333333333333333333333333333333333333333333333333333333333333",
    "destination": "nexus.example.org/helper@sha256:3333333333333333333333333333333333333333333333333333333333333333",
    "version": "19.5.2"
  }
}
EOF

toml="$(python3 "${root}/scripts/gitlab_build_config.py" "${contract}")"
printf '%s' "${toml}" | grep -F 'name = "verjson-candidate-acquisition"' >/dev/null
printf '%s' "${toml}" | grep -F 'mount_path = "/etc/verjson-candidate-acquisition"' >/dev/null
printf '%s' "${toml}" | grep -F 'enable_service_links = false' >/dev/null
printf '%s' "${toml}" | grep -F '"verjson.io/isolation" = "restricted"' >/dev/null
! printf '%s' "${toml}" | grep -E 'volumes\.(host_path|secret|pvc|csi|nfs)|docker\.sock|DOCKER_AUTH_CONFIG=' >/dev/null

egress="$(python3 "${root}/scripts/gitlab_build_config.py" --egress "${contract}")"
printf '%s' "${egress}" | python3 -c '
import json, sys
policy = json.load(sys.stdin)
assert policy["kind"] == "NetworkPolicy"
assert policy["metadata"]["namespace"] == "gitlab-jobs"
assert policy["spec"]["ingress"] == []
assert "secret" not in json.dumps(policy).lower()
print("GitLab generator isolation contract passed")
'
