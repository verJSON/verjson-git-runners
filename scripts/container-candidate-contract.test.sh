#!/usr/bin/env bash
# GENERATED FILE — do not edit by hand.
# Contract: b12cc46b8439d1573fcc32cf595854530361641b
# Regenerate with:
#   scripts/gen-container-candidate.sh contract-test b12cc46b8439d1573fcc32cf595854530361641b container-candidate.json > scripts/container-candidate-contract.test.sh
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
caller="$root/.github/workflows/container-candidate.yml"
validator="$root/scripts/container_release_manifest.py"
destination_helper="$root/scripts/container_registry_destinations.py"
fail() { echo "ERROR: $*" >&2; exit 1; }

[ -f "$caller" ] || fail "generated caller is missing"
[ -f "$validator" ] || fail "generated validator is missing"
[ -f "$destination_helper" ] || fail "generated destination helper is missing"
grep -qx '# Contract: b12cc46b8439d1573fcc32cf595854530361641b' "$caller" || fail "caller contract pin differs"
grep -qx '# Contract: b12cc46b8439d1573fcc32cf595854530361641b' "$validator" || fail "validator contract pin differs"
grep -qx '# Contract: b12cc46b8439d1573fcc32cf595854530361641b' "$destination_helper" || fail "destination helper contract pin differs"
[ "$(grep -c 'uses: Verjson/.github/.github/workflows/container-candidate.yml@b12cc46b8439d1573fcc32cf595854530361641b' "$caller")" -eq 1 ] || fail "validation does not use the pinned read-only reusable workflow"
[ "$(grep -c 'uses: Verjson/.github/.github/workflows/container-candidate-publish.yml@b12cc46b8439d1573fcc32cf595854530361641b' "$caller")" -eq 1 ] || fail "publication does not use the pinned publication reusable workflow"
[ "$(grep -c 'contract-ref: b12cc46b8439d1573fcc32cf595854530361641b' "$caller")" -eq 2 ] || fail "caller does not pass the shared pin to both event paths"
[ "$(grep -c 'cleanup-unused-docker-images: false' "$caller")" -eq 2 ] || fail "caller does not pass the reviewed cleanup setting to both event paths"
[ "$(grep -c 'acquisition-sha256: a9b27a03b4283fff264a23b62f79f731ae1182d85eaa3aded31bd3b224fc2256' "$caller")" -eq 1 ] || fail "only trusted publication may pin the acquisition implementation digest"
[ "$(grep -c 'transfer-sha256: 6bbd22f2e0c4814d661cb74e1e31e6ed1cb9b5cf744b35571749221579c0b14a' "$caller")" -eq 1 ] || fail "trusted publication does not pin the dependency transfer implementation digest"
[ "$(grep -c 'disk-sha256: 728f26343beb7189c5522eebceb639c35e0eb37b2df20e4affa2c559918af160' "$caller")" -eq 1 ] || fail "trusted publication does not pin disk diagnostics implementation digest"
[ "$(grep -c 'retry-sha256: dcc9bbb4e257ae782949936ad503455d0396e95e74da781c62a8d1a7227a0552' "$caller")" -eq 2 ] || fail "both event paths do not pin the retry verifier digest"
[ "$(grep -c '^      actions: read$' "$caller")" -eq 1 ] || fail "pull-request validation requires Actions reads"
[ "$(grep -c '^      actions: write$' "$caller")" -eq 1 ] || fail "only publication may delete its transfer cache"
[ "$(grep -c '^      contents: read$' "$caller")" -eq 2 ] || fail "both event paths require source reads"
[ "$(grep -c 'provenance-sha256: e785ad9fb49d60d0de25dd2214e2c03fbf7fa348a7df2407ee7f187757a91c74' "$caller")" -eq 1 ] || fail "publication does not pin provenance helper"
[ "$(grep -c 'promotionEligible:false' "$caller")" -eq 0 ] || fail "caller may not assert candidate eligibility"
! grep -q '^      attestations: write$' "$caller" || fail "caller may not request GitHub Artifact Attestations"
[ "$(grep -c '^      packages: write$' "$caller")" -eq 1 ] || fail "only publication may write candidate images"
[ "$(grep -c '^      id-token: write$' "$caller")" -eq 1 ] || fail "only publication may mint attestation identity"
grep -q "if: github.event_name == 'pull_request'" "$caller" || fail "validation is not restricted to pull requests"
grep -q "if: github.event_name == 'push' && github.ref == 'refs/heads/main'" "$caller" || fail "publication is not restricted to trusted main pushes"
[ "$(sha256sum "$caller" | cut -d' ' -f1)" = "ff75555afdc076ab11a798fec055976a94e3359a7b1e83581fd1360218d2d4df" ] || fail "generated caller was edited"
[ "$(sha256sum "$validator" | cut -d' ' -f1)" = "f63fdaa8c5896969689dd1e50656e5ae0536dd748986a9bacf7878809f52cad7" ] || fail "generated validator was edited"
[ "$(sha256sum "$destination_helper" | cut -d' ' -f1)" = "a4d776fce5fc0c26657df20673c3e20f0f03b1916f2fee22d43669202bebbdfc" ] || fail "generated destination helper was edited"
if grep -Eq 'secrets: inherit|registry-namespace:|environment:' "$caller"; then
  fail "caller may not inherit credentials or inject registry namespaces or environments"
fi
if [ "false" = true ]; then
  [ "$(grep -cF 'NODE_AUTH_TOKEN: ${{ secrets.NODE_AUTH_TOKEN }}' "$caller")" -eq 1 ] || fail "private-package caller must route its acquisition token only to trusted publication"
validation_job="$(mktemp)"
awk '/^  validate:/{copy=1} /^  publish:/{copy=0} copy' "$caller" > "$validation_job"
if grep -Eq 'packages: read|secrets:|NODE_AUTH_TOKEN' "$validation_job"; then
    rm -f "$validation_job"
    fail "private-package pull-request validation exposes package credentials or contents"
  fi
  rm -f "$validation_job"
else
  ! grep -q 'NODE_AUTH_TOKEN\|packages: read' "$caller" || fail "public-only caller exposes package credentials or read authority"
fi
# Publication signs as Verjson/.github/.github/workflows/container-candidate-publish.yml@b12cc46b8439d1573fcc32cf595854530361641b and refuses any other declared identity, but
# only after building and publishing; a stale identity fails here first.
[ -f "$root/container-candidate.json" ] || fail "candidate config container-candidate.json is missing"
python3 -I -c '
import json, sys
with open(sys.argv[1], encoding="utf-8") as stream:
    config = json.load(stream)
images = config.get("images") if isinstance(config, dict) else None
sys.exit(0 if isinstance(images, list) and images and all(
    isinstance(image, dict) and isinstance(image.get("provenance"), dict)
    and image["provenance"].get("builderIdentity") == sys.argv[2]
    for image in images) else 1)
' "$root/container-candidate.json" 'Verjson/.github/.github/workflows/container-candidate-publish.yml@b12cc46b8439d1573fcc32cf595854530361641b'   || fail "every image in container-candidate.json must declare provenance.builderIdentity Verjson/.github/.github/workflows/container-candidate-publish.yml@b12cc46b8439d1573fcc32cf595854530361641b, the publishing entrypoint at this contract"
python3 "$validator" --help >/dev/null
echo "container candidate generated contract passed"
