#!/usr/bin/env bash
set -euo pipefail

workflow_root="$(cd "$(dirname "$0")/../.github/workflows" && pwd)"
legacy_prefix='VERJSON_'
legacy_release_token='RELEASE_'"TOKEN"

require_no_match() {
  local description="$1" status=0
  shift
  grep "$@" >/dev/null || status=$?
  case "$status" in
    0) printf 'Forbidden %s\n' "$description" >&2; return 1 ;;
    1) return 0 ;;
    *) printf 'Could not check %s (grep status %s)\n' "$description" "$status" >&2; return "$status" ;;
  esac
}

require_no_match 'legacy workflow reference' -RE "vars\\.${legacy_prefix}|secrets\\.${legacy_prefix}(${legacy_release_token}|RUNNER_DEPLOY_TOKEN)" "$workflow_root"
grep -Fq 'vars.CI_LANE_PRIVILEGED' "$workflow_root/ai-privileged-merge.yml"
grep -Fq 'release_app_client_id: ${{ vars.RELEASE_APP_CLIENT_ID }}' "$workflow_root/container-release.yml"
grep -Fq 'release_environment: release-app' "$workflow_root/container-release.yml"
grep -Fq 'secrets: inherit' "$workflow_root/container-release.yml"
require_no_match 'obsolete release token' -F "secrets.${legacy_release_token}" "$workflow_root/container-release.yml"
require_no_match 'private release app key' -F 'release_app_private_key: ${{ secrets.RELEASE_APP_PRIVATE_KEY }}' "$workflow_root/container-release.yml"
