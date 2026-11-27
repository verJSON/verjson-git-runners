#!/usr/bin/env python3
"""Behavioral tests for scripts/runner-deployment-evidence.py.

This adapter runs in the deployment controller's stripped subprocess sandbox
(`PATH`, `LANG`, `LC_ALL`, `TMPDIR`, `SSL_CERT_FILE`, `SSL_CERT_DIR` only — no
`GH_TOKEN`, no App JWT). Every GitHub read it performs is therefore an
unauthenticated public-API call; these tests stub that boundary and never hit
the network.
"""
from __future__ import annotations

import contextlib
import hashlib
import http.client
import importlib.util
import io
import json
import subprocess
import sys
import traceback
import unittest
import urllib.error
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "scripts" / "runner-deployment-evidence.py"
SPEC = importlib.util.spec_from_file_location("runner_deployment_evidence", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
EVIDENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVIDENCE)
with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
    from container_deployment_controller import DeploymentError, ProcessAdapter

MANIFEST_IDENTITY = "sha256:" + "a" * 64
MANIFEST_BYTES = json.dumps({"releaseVersion": "1.2.3", "images": []}, sort_keys=True).encode("utf-8")
REAL_DIGEST = "sha256:" + hashlib.sha256(MANIFEST_BYTES).hexdigest()


def _make_repo(tmp: Path, *, manifest_bytes: bytes = MANIFEST_BYTES) -> Path:
    (tmp / "RELEASES" / "containers").mkdir(parents=True)
    (tmp / "RELEASES" / "containers" / "v1.2.3.json").write_bytes(manifest_bytes)
    (tmp / "container-deployment.json").write_text(
        json.dumps({"expectedRelease": {"sourceRepository": "Verjson/example"}}),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=tmp, check=True)
    return tmp


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc) -> None:
        return None


def _release_tags_payload(asset_id: int = 42, size: int | None = None) -> bytes:
    return json.dumps({
        "assets": [
            {"id": asset_id, "name": "release-manifest.json", "size": size if size is not None else len(MANIFEST_BYTES)},
            {"id": 7, "name": "base-sbom.json", "size": 100},
        ],
    }).encode("utf-8")


def _opener_sequence(*responses):
    iterator = iter(responses)

    def opener(request, timeout=30):
        value = next(iterator)
        if isinstance(value, Exception):
            raise value
        return _FakeResponse(value)

    return opener


class GitHeadTest(unittest.TestCase):
    def test_reports_the_exact_checked_out_commit_and_tree(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            expected_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True,
            ).stdout.strip()
            expected_tree = subprocess.run(
                ["git", "rev-parse", "HEAD^{tree}"], cwd=repo, check=True, capture_output=True, text=True,
            ).stdout.strip()
            self.assertEqual(EVIDENCE.git_head_commit(repo), expected_commit)
            self.assertEqual(EVIDENCE.git_head_tree(repo), expected_tree)


class FindLocalManifestTest(unittest.TestCase):
    def test_finds_the_release_file_whose_digest_matches(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            version, raw_bytes = EVIDENCE.find_local_manifest(repo, REAL_DIGEST)
            self.assertEqual(version, "1.2.3")
            self.assertEqual(raw_bytes, MANIFEST_BYTES)

    def test_raises_when_no_local_manifest_matches_the_requested_digest(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            other_digest = "sha256:" + "b" * 64
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.find_local_manifest(repo, other_digest)

    def test_raises_when_releases_directory_is_absent(self) -> None:
        with TemporaryDirectory() as raw:
            repo = Path(raw)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.find_local_manifest(repo, REAL_DIGEST)

    def test_raises_when_a_locally_retained_manifest_is_not_valid_json(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            malformed = b"not json"
            digest = "sha256:" + hashlib.sha256(malformed).hexdigest()
            (repo / "RELEASES" / "containers" / "v1.2.3.json").write_bytes(malformed)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.find_local_manifest(repo, digest)

    def test_rejects_a_release_version_outside_stable_semver(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            malicious = json.dumps({"releaseVersion": "1.2.3/../../evil"}, sort_keys=True).encode()
            digest = "sha256:" + hashlib.sha256(malicious).hexdigest()
            (repo / "RELEASES" / "containers" / "v1.2.3.json").write_bytes(malicious)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.find_local_manifest(repo, digest)


class FetchReleaseAssetIdTest(unittest.TestCase):
    def test_returns_the_release_manifest_asset_id_and_size(self) -> None:
        opener = _opener_sequence(_release_tags_payload(asset_id=532627568, size=9093))
        asset_id, size = EVIDENCE.fetch_release_asset_id("Verjson/example", "1.2.3", opener=opener)
        self.assertEqual(asset_id, 532627568)
        self.assertEqual(size, 9093)

    def test_raises_when_no_release_manifest_asset_is_present(self) -> None:
        payload = json.dumps({"assets": [{"id": 1, "name": "other.json", "size": 5}]}).encode("utf-8")
        opener = _opener_sequence(payload)
        with self.assertRaises(EVIDENCE.EvidenceError):
            EVIDENCE.fetch_release_asset_id("Verjson/example", "1.2.3", opener=opener)

    def test_raises_on_http_error(self) -> None:
        opener = _opener_sequence(urllib.error.HTTPError("url", 404, "not found", {}, io.BytesIO()))
        with self.assertRaises(EVIDENCE.EvidenceError):
            EVIDENCE.fetch_release_asset_id("Verjson/example", "1.2.3", opener=opener)


class FetchAssetBytesTest(unittest.TestCase):
    def test_returns_the_raw_asset_bytes(self) -> None:
        opener = _opener_sequence(MANIFEST_BYTES)
        result = EVIDENCE.fetch_asset_bytes("Verjson/example", 42, opener=opener)
        self.assertEqual(result, MANIFEST_BYTES)

    def test_raises_on_http_error(self) -> None:
        opener = _opener_sequence(urllib.error.HTTPError("url", 500, "boom", {}, io.BytesIO()))
        with self.assertRaises(EVIDENCE.EvidenceError):
            EVIDENCE.fetch_asset_bytes("Verjson/example", 42, opener=opener)


class CollectEvidenceTest(unittest.TestCase):
    def test_returns_evidence_matching_the_requested_manifest_identity(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            opener = _opener_sequence(_release_tags_payload(asset_id=99), MANIFEST_BYTES)
            evidence = EVIDENCE.collect_evidence(repo, REAL_DIGEST, "", opener=opener)
            self.assertEqual(evidence["manifestIdentity"], REAL_DIGEST)
            self.assertEqual(evidence["releaseAssetId"], 99)
            self.assertEqual(evidence["manifestBytes"], MANIFEST_BYTES.decode("utf-8"))
            self.assertEqual(evidence["manifest"], json.loads(MANIFEST_BYTES))
            self.assertEqual(evidence["workflowRunAttempt"], 1)
            self.assertIn("headCommit", evidence)
            self.assertIn("headTree", evidence)

    def test_rejects_a_malformed_manifest_identity(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.collect_evidence(repo, "not-a-digest", "", opener=_opener_sequence())

    def test_rejects_when_downloaded_bytes_differ_from_the_requested_digest(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            tampered = MANIFEST_BYTES + b" "
            opener = _opener_sequence(_release_tags_payload(asset_id=1, size=len(tampered)), tampered)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.collect_evidence(repo, REAL_DIGEST, "", opener=opener)

    def test_rejects_when_downloaded_bytes_differ_from_the_locally_retained_manifest(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            # Same digest as requested, but not byte-identical to the local file —
            # can only happen if the local file itself was tampered with.
            other = json.dumps({"releaseVersion": "1.2.3", "images": [], "x": 1}, sort_keys=True).encode()
            digest = "sha256:" + hashlib.sha256(other).hexdigest()
            (repo / "RELEASES" / "containers" / "v1.2.3.json").write_bytes(other)
            opener = _opener_sequence(_release_tags_payload(asset_id=1, size=len(MANIFEST_BYTES)), MANIFEST_BYTES)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.collect_evidence(repo, digest, "", opener=opener)

    def test_rejects_when_downloaded_size_differs_from_reviewed_metadata(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            opener = _opener_sequence(_release_tags_payload(asset_id=1, size=999999), MANIFEST_BYTES)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.collect_evidence(repo, REAL_DIGEST, "", opener=opener)

    def test_raises_a_clear_error_for_rollback_receipt_requests(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            with self.assertRaises(EVIDENCE.EvidenceError) as context:
                EVIDENCE.collect_evidence(repo, REAL_DIGEST, "sha256:" + "c" * 64, opener=_opener_sequence())
            self.assertIn("rollback", str(context.exception).lower())

    def test_raises_when_config_is_missing(self) -> None:
        with TemporaryDirectory() as raw:
            repo = Path(raw)
            (repo / "RELEASES" / "containers").mkdir(parents=True)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.collect_evidence(repo, REAL_DIGEST, "", opener=_opener_sequence())

    def test_raises_a_clean_error_when_asset_bytes_are_not_valid_utf8(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            # Valid JSON per RFC 8259 (UTF-16 with BOM) but not valid UTF-8 bytes
            # (0xFF is never a valid UTF-8 byte): json.loads() auto-detects and
            # strips the BOM/encoding and parses it, so a decode guard is needed
            # downstream to avoid an uncaught UnicodeDecodeError.
            weird = json.dumps({"releaseVersion": "1.2.3"}).encode("utf-16")
            digest = "sha256:" + hashlib.sha256(weird).hexdigest()
            (repo / "RELEASES" / "containers" / "v1.2.3.json").write_bytes(weird)
            opener = _opener_sequence(_release_tags_payload(asset_id=1, size=len(weird)), weird)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.collect_evidence(repo, digest, "", opener=opener)

    def test_raises_when_the_release_asset_metadata_is_not_json(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            opener = _opener_sequence(b"not json at all")
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.collect_evidence(repo, REAL_DIGEST, "", opener=opener)

    def test_raises_when_the_release_manifest_asset_id_has_the_wrong_type(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            payload = json.dumps({
                "assets": [{"id": "not-an-int", "name": "release-manifest.json", "size": len(MANIFEST_BYTES)}],
            }).encode("utf-8")
            opener = _opener_sequence(payload)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.collect_evidence(repo, REAL_DIGEST, "", opener=opener)

    def test_raises_when_the_release_manifest_asset_size_has_the_wrong_type(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            payload = json.dumps({
                "assets": [{"id": 1, "name": "release-manifest.json", "size": "not-an-int"}],
            }).encode("utf-8")
            opener = _opener_sequence(payload)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.collect_evidence(repo, REAL_DIGEST, "", opener=opener)

    def test_raises_when_expected_release_source_repository_is_missing(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            (repo / "container-deployment.json").write_text(json.dumps({"expectedRelease": {}}), encoding="utf-8")
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.collect_evidence(repo, REAL_DIGEST, "", opener=_opener_sequence())


class MainTest(unittest.TestCase):
    def test_emits_one_json_object_on_stdout_and_exits_zero(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            opener = _opener_sequence(_release_tags_payload(asset_id=1), MANIFEST_BYTES)
            with patch.object(EVIDENCE, "DEFAULT_ROOT", repo), patch.object(
                EVIDENCE.urllib.request, "urlopen", opener
            ):
                exit_code = EVIDENCE.main(["--manifest-identity", REAL_DIGEST, "--fleet", "github-canary"])
            self.assertEqual(exit_code, 0)

    def test_exits_nonzero_and_reports_on_stderr_when_evidence_cannot_be_collected(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            with patch.object(EVIDENCE, "DEFAULT_ROOT", repo):
                exit_code = EVIDENCE.main(["--manifest-identity", "bad", "--fleet", "github-canary"])
            self.assertEqual(exit_code, 1)


class ControllerRelayTest(unittest.TestCase):
    provider_text = "https://provider.example/download?token=synthetic-private-value"

    def assert_relayed(self, opener, diagnostic, *, git_failure=None):
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            command = ["python3", "scripts/runner-deployment-evidence.py", "--manifest-identity",
                       REAL_DIGEST, "--fleet", "github-canary"]
            git_run = subprocess.run

            def run_git(args, **kwargs):
                if git_failure is not None and args[-1] == git_failure[0]:
                    raise git_failure[1]
                return git_run(args, **kwargs)

            def invoke(args, *, timeout_seconds):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    try:
                        status = EVIDENCE.main(args[2:])
                    except (OSError, http.client.HTTPException, subprocess.CalledProcessError):
                        traceback.print_exc()
                        status = 1
                self.assertNotEqual(status, 0)
                raise subprocess.CalledProcessError(status, args, stderr=stderr.getvalue())

            with patch.object(EVIDENCE, "DEFAULT_ROOT", repo), \
                    patch.object(EVIDENCE.urllib.request, "urlopen", opener), \
                    patch.object(EVIDENCE.subprocess, "run", side_effect=run_git), \
                    patch.object(ProcessAdapter, "_invoke", side_effect=invoke), \
                    self.assertRaises(DeploymentError) as rejected:
                ProcessAdapter._run(command)
            self.assertEqual(str(rejected.exception), f"adapter command failed: {diagnostic}")

    def test_relays_fixed_http_diagnostics_for_each_release_stage(self):
        for stages, operation in (
            ((), "GitHub release metadata request"),
            ((_release_tags_payload(),), "GitHub release manifest download"),
        ):
            for code in (403, 429):
                with self.subTest(operation=operation, code=code):
                    failure = urllib.error.HTTPError(self.provider_text, code, self.provider_text, {}, io.BytesIO())
                    self.assert_relayed(_opener_sequence(*stages, failure), f"{operation} failed (HTTP {code})")
                    self.assertTrue(failure.fp.closed)

    def test_relays_network_diagnostics_without_dns_reason(self):
        for stages, operation in (
            ((), "GitHub release metadata request"),
            ((_release_tags_payload(),), "GitHub release manifest download"),
        ):
            with self.subTest(operation=operation):
                failure = urllib.error.URLError(self.provider_text)
                self.assert_relayed(_opener_sequence(*stages, failure), f"{operation} is unreachable")

    def test_relays_network_diagnostics_when_response_read_fails(self):
        for stages, operation in (
            ((), "GitHub release metadata request"),
            ((_FakeResponse(_release_tags_payload()),), "GitHub release manifest download"),
        ):
            for error in (TimeoutError(self.provider_text), http.client.IncompleteRead(b"untrusted response")):
                with self.subTest(operation=operation, error=type(error).__name__):
                    response = _FakeResponse(b"")
                    responses = iter((*stages, response))
                    with patch.object(response, "read", side_effect=error):
                        self.assert_relayed(lambda request, timeout: next(responses), f"{operation} is unreachable")

    def test_relays_no_status_when_http_error_contains_no_valid_error_code(self):
        for code in (200, True, self.provider_text):
            with self.subTest(code=code):
                failure = urllib.error.HTTPError(self.provider_text, code, self.provider_text, {}, io.BytesIO())
                self.assert_relayed(_opener_sequence(failure), "GitHub release metadata request failed")

    def test_relays_malformed_release_metadata_without_the_url(self):
        self.assert_relayed(_opener_sequence(b"untrusted non JSON body"),
                            "GitHub release metadata response is not valid JSON")

    def test_relays_fixed_checkout_diagnostics_when_git_fails(self):
        for revision, label, failure in (
            ("HEAD", "commit", subprocess.CalledProcessError(128, ["git"], stderr=self.provider_text)),
            ("HEAD^{tree}", "tree", OSError(self.provider_text)),
        ):
            with self.subTest(revision=revision):
                opener = _opener_sequence(_release_tags_payload(), MANIFEST_BYTES)
                self.assert_relayed(opener, f"runner evidence checkout {label} lookup failed",
                                    git_failure=(revision, failure))


if __name__ == "__main__":
    unittest.main()
