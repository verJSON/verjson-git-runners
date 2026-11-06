---
date: 2026-11-05
issue: 248
impact: patch
title: Regenerate the canonical adopter set at contract v4.4.0
---

Regenerate every generated contract artifact this repository carries at `verJSON/.github` release v4.4.0 (`b12cc46b8439d1573fcc32cf595854530361641b`), replacing four mixed pins (`2d1ea177`, `645e5c23`, `3b83ddea`, `737250a7`). The set covers the changelog callers, renderer, ADR index, contract test and the generated `.github/CODEOWNERS` (`* @verJSON/devs`). It also covers the container candidate, release and protected deployment callers and helpers, and the AI review, re-arm and privileged-merge callers.

- **Changelog gate.** A pull request now needs a new valid fragment for any change except changelog stores and test-only files. That includes workflows, docs, configuration and dependency pin bumps. The old pin required a fragment only for dependency and production-source changes, and only warned for workflows.
- **AI review.** The caller now calls a reusable review that compares repository identity case-insensitively (`65529002`). That repairs the `arm run provenance mismatch` failures. The caller also gains an `allow_absent_checks` input and per-pull-request `concurrency` with `cancel-in-progress`.
- **Lifecycle re-arm.** This caller now targets the canonical re-arm at the contract SHA instead of the local head-transition caller (ADR 0164 amendment).
- **Container provenance.** Provenance is now keyless Cosign/Sigstore bundles attached as OCI referrers (`verJSON/.github` ADR 0216). Both the candidate and release callers drop `attestations: write`. The candidate publish job now pins the provenance helper by digest, and it gains `actions: write` to delete its one-time dependency-transfer cache.
- **Pins.** The image `builderIdentity`, the vendored `scripts/changelog.py`, and the repository's own pin and digest tests move to the same revision.
