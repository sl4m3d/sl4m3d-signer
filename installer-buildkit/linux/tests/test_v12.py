from __future__ import annotations
import json
from pathlib import Path

import pytest

import crypto_core as core
import stats_client


def test_stats_disabled_by_default_never_calls_network(tmp_path, monkeypatch):
    monkeypatch.setattr(stats_client, "SETTINGS_FILE", tmp_path / "statistics.json")
    called = []
    monkeypatch.setattr(stats_client.urllib.request, "urlopen", lambda *a, **k: called.append((a, k)))
    assert stats_client.is_enabled() is False
    stats_client.record_successful_signature()
    assert called == []
    assert stats_client.pending_count() == 0


def test_stats_posts_only_aggregate_event_and_version(tmp_path, monkeypatch):
    monkeypatch.setattr(stats_client, "SETTINGS_FILE", tmp_path / "statistics.json")
    captured = []

    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, limit=4096): return b'{"ok":true,"count":1}'

    def fake_urlopen(request, timeout):
        captured.append((request, timeout))
        return Response()

    monkeypatch.setattr(stats_client.urllib.request, "urlopen", fake_urlopen)
    stats_client.set_enabled(True)
    stats_client.record_successful_signature()
    assert stats_client.pending_count() == 0
    assert len(captured) == 1
    request, timeout = captured[0]
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {"event": "cms_sign", "version": "1.2.0"}
    assert timeout <= 2.0
    assert "Cookie" not in request.headers
    assert "filename" not in request.data.decode().lower()
    assert "path" not in request.data.decode().lower()
    assert "certificate" not in request.data.decode().lower()
    assert "password" not in request.data.decode().lower()
    assert "Authorization" in request.headers and request.headers["Authorization"].startswith("Bearer sb_publishable_")
    assert (tmp_path / "statistics.json").exists()


def test_stats_queue_survives_offline_and_disable_clears_it(tmp_path, monkeypatch):
    monkeypatch.setattr(stats_client, "SETTINGS_FILE", tmp_path / "statistics.json")
    def fail(*_args, **_kwargs): raise OSError("offline")
    monkeypatch.setattr(stats_client.urllib.request, "urlopen", fail)
    stats_client.set_enabled(True)
    stats_client.record_successful_signature()
    assert stats_client.pending_count() == 1
    stats_client.set_enabled(False)
    assert stats_client.pending_count() == 0
    assert not stats_client.is_enabled()


def test_cer_only_preserves_existing_p12_and_exports_der(tmp_path):
    existing_p12 = tmp_path / "cer_only_case.p12"
    existing_p12.write_bytes(b"user-owned-existing-file")
    cert, identity = core.create_certificate("CER only case", 30, "RSA 2048", tmp_path, export_identity=False)
    assert identity is None
    assert cert.read_bytes()[0] == 0x30
    assert existing_p12.read_bytes() == b"user-owned-existing-file"
    assert core.inspect_certificate(cert)


def test_streaming_sign_and_verify_32_mib_payload(tmp_path):
    export = tmp_path / "identity"
    export.mkdir()
    _, p12 = core.create_certificate("large payload test", 3, "RSA 2048", export, "long-test-password")
    assert p12 is not None
    original = tmp_path / "large.bin"
    block = bytes(range(256)) * 1024
    with original.open("wb") as handle:
        for _ in range(128):  # 32 MiB
            handle.write(block)
    signed = tmp_path / "large.signed.p7m"
    extracted = tmp_path / "large.extracted.bin"
    core.sign_file(original, p12, "long-test-password", signed)
    core.verify_cms(signed, extracted)
    def digest(path):
        import hashlib
        h=hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.digest()
    assert original.stat().st_size == 32 * 1024 * 1024
    assert digest(original) == digest(extracted)
