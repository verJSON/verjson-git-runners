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
for mount in verjson-candidate-acquisition verjson-candidate-execution verjson-dependency-acquisition; do
  printf '%s' "${toml}" | grep -F "name = \"${mount}\"" >/dev/null
  printf '%s' "${toml}" | grep -F "mount_path = \"/etc/${mount}\"" >/dev/null
done
printf '%s' "${toml}" | grep -F 'read_only = true' >/dev/null
printf '%s' "${toml}" | grep -F 'enable_service_links = false' >/dev/null
printf '%s' "${toml}" | grep -F '"verjson.io/isolation" = "restricted"' >/dev/null
! printf '%s' "${toml}" | grep -E 'volumes\.(host_path|secret|pvc|csi|nfs)|docker\.sock|DOCKER_AUTH_CONFIG=' >/dev/null

egress="$(python3 "${root}/scripts/gitlab_build_config.py" --egress "${contract}")"
printf '%s' "${egress}" | python3 -c '
import json, sys
from pathlib import Path

policy = json.load(sys.stdin)
assert policy["kind"] == "NetworkPolicy"
assert policy["metadata"]["namespace"] == "gitlab-jobs"
assert policy["spec"]["ingress"] == []
assert "secret" not in json.dumps(policy).lower()
egress = policy["spec"]["egress"]
assert egress[0]["to"][0]["podSelector"] == {"matchLabels": {"k8s-app": "kube-dns"}}
public = egress[1]["to"][0]["ipBlock"]
assert public["cidr"] == "0.0.0.0/0"
assert egress[1]["ports"] == [{"protocol": "TCP", "port": 443}]
root = Path(sys.argv[1])
isolation = next(
    item
    for item in json.loads((root / "deploy/gitlab/runner.json").read_text())["items"]
    if item.get("kind") == "NetworkPolicy" and item["metadata"]["name"] == "runner-isolation"
)
reviewed = next(
    rule["to"][0]["ipBlock"]
    for rule in isolation["spec"]["egress"]
    if rule.get("to") and "ipBlock" in rule["to"][0]
)
assert public["except"] == reviewed["except"], (public["except"], reviewed["except"])
reviewed_ports = next(
    rule["ports"]
    for rule in isolation["spec"]["egress"]
    if rule.get("to") and "ipBlock" in rule["to"][0]
)
assert egress[1]["ports"] == reviewed_ports
serialized = json.dumps(policy).lower()
assert "traefik" not in serialized
assert "8443" not in serialized
print("GitLab generator isolation contract passed")
' "${root}"
