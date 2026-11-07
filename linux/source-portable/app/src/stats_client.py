"""Optional aggregate signature counter. No file or identity data is ever read here."""
from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from pathlib import Path

import crypto_core as core

API_URL = "https://pwwvcxgixendhavaszco.supabase.co/functions/v1/signer-stats"
# Supabase publishable key. It is intentionally public; authorization is enforced by the Edge Function.
API_KEY = "sb_publishable_Kd6GlHTgiwjHuoLSyy_6rA_rlw88xOh"
SETTINGS_FILE = core.DATA_DIR / "statistics.json"
_LOCK = threading.Lock()


def _load() -> dict:
    try:
        value = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            return {
                "enabled": value.get("enabled") is True,
                "pending": max(0, min(100000, int(value.get("pending", 0)))),
            }
    except Exception:
        pass
    return {"enabled": False, "pending": 0}


def _save(data: dict) -> None:
    tmp = SETTINGS_FILE.with_name(SETTINGS_FILE.name + ".new")
    try:
        tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        if os.name != "nt":
            os.chmod(tmp, 0o600)
        os.replace(tmp, SETTINGS_FILE)
    finally:
        tmp.unlink(missing_ok=True)


def is_enabled() -> bool:
    with _LOCK:
        return _load()["enabled"]


def pending_count() -> int:
    with _LOCK:
        return _load()["pending"]


def set_enabled(enabled: bool) -> None:
    with _LOCK:
        data = _load()
        data["enabled"] = bool(enabled)
        if not enabled:
            # Do not send events that were queued under a previous consent state.
            data["pending"] = 0
        _save(data)


def record_successful_signature() -> None:
    """Queue one already-verified signature and attempt a short best-effort sync."""
    with _LOCK:
        data = _load()
        if not data["enabled"]:
            return
        data["pending"] = min(100000, data["pending"] + 1)
        _save(data)
    flush_pending()


def flush_pending() -> int:
    """Send only an event type and application version. Keep events on any failure."""
    sent = 0
    # Keep the lock across the send to prevent two UI/background syncs consuming the same queue.
    with _LOCK:
        data = _load()
        if not data["enabled"]:
            return 0
        pending = data["pending"]
        while pending > 0:
            body = json.dumps({"event": "cms_sign", "version": core.APP_VERSION}).encode("utf-8")
            request = urllib.request.Request(
                API_URL,
                data=body,
                method="POST",
                headers={
                    "apikey": API_KEY,
                    "Authorization": "Bearer " + API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Cache-Control": "no-store",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=2.0) as response:
                    result = json.loads(response.read(4096).decode("utf-8"))
                    if response.status < 200 or response.status >= 300 or result.get("ok") is not True:
                        break
            except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError):
                break
            pending -= 1
            sent += 1
            data["pending"] = pending
            _save(data)
        return sent
