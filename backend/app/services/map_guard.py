from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal


MapMode = Literal["OPEN_3D", "PHOTOREALISTIC"]


_LOCK = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _usage_path() -> Path:
    default = Path(__file__).resolve().parents[3] / "backend-cache" / "google-map-usage.json"
    return Path(os.getenv("GOOGLE_MAP_USAGE_PATH", str(default)))


def _limit(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _load_usage(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_usage(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    with temporary_path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
    os.replace(temporary_path, path)


def _reset_period_counters(usage: dict[str, Any], now: datetime) -> None:
    month = now.strftime("%Y-%m")
    day = now.strftime("%Y-%m-%d")
    hour = now.strftime("%Y-%m-%dT%H")
    if usage.get("month") != month:
        usage["month"] = month
        usage["monthSessions"] = 0
    if usage.get("day") != day:
        usage["day"] = day
        usage["daySessions"] = 0
    if usage.get("hour") != hour:
        usage["hour"] = hour
        usage["hourSessions"] = 0


def _fallback(reason: str, *, limits: dict[str, int]) -> dict[str, Any]:
    return {
        "mode": "OPEN_3D",
        "googleMapsApiKey": None,
        "styleUrl": os.getenv("MAP_STYLE_URL", "https://tiles.openfreemap.org/styles/liberty").strip() or "https://tiles.openfreemap.org/styles/liberty",
        "sessionId": None,
        "expiresAt": None,
        "reused": False,
        "reason": reason,
        "limits": limits,
    }


def acquire_map_session(requested_mode: MapMode = "PHOTOREALISTIC") -> dict[str, Any]:
    """Return a safe OpenFreeMap style config unless photorealistic mode is explicitly guarded."""
    limits = {
        "monthly": _limit("GOOGLE_PHOTOREALISTIC_MONTHLY_SESSION_LIMIT", 900),
        "daily": _limit("GOOGLE_PHOTOREALISTIC_DAILY_SESSION_LIMIT", 100),
        "hourly": _limit("GOOGLE_PHOTOREALISTIC_HOURLY_SESSION_LIMIT", 30),
    }
    if requested_mode != "PHOTOREALISTIC":
        return _fallback("OPEN_3D requested", limits=limits)
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if os.getenv("GOOGLE_PHOTOREALISTIC_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"} or not api_key:
        return _fallback("Photorealistic mode disabled or API key missing", limits=limits)

    now = _now()
    session_hours = max(1.0, float(os.getenv("GOOGLE_PHOTOREALISTIC_SESSION_HOURS", "3")))
    path = _usage_path()
    with _LOCK:
        usage = _load_usage(path)
        _reset_period_counters(usage, now)
        active = usage.get("activeSession")
        if isinstance(active, dict):
            try:
                expires_at = datetime.fromisoformat(str(active["expiresAt"]))
            except (KeyError, TypeError, ValueError):
                expires_at = now
            if expires_at > now:
                return {
                    "mode": "PHOTOREALISTIC",
                    "googleMapsApiKey": api_key,
                    "styleUrl": os.getenv("MAP_STYLE_URL", "https://tiles.openfreemap.org/styles/liberty").strip() or "https://tiles.openfreemap.org/styles/liberty",
                    "sessionId": str(active.get("sessionId")),
                    "expiresAt": expires_at.isoformat().replace("+00:00", "Z"),
                    "reused": True,
                    "reason": "Existing guarded Google session reused",
                    "limits": limits,
                }

        if usage.get("monthSessions", 0) >= limits["monthly"]:
            return _fallback("Monthly Photorealistic session limit reached", limits=limits)
        if usage.get("daySessions", 0) >= limits["daily"]:
            return _fallback("Daily Photorealistic session limit reached", limits=limits)
        if usage.get("hourSessions", 0) >= limits["hourly"]:
            return _fallback("Hourly Photorealistic session limit reached", limits=limits)

        expires_at = now + timedelta(hours=session_hours)
        session_id = uuid.uuid4().hex
        usage["monthSessions"] = int(usage.get("monthSessions", 0)) + 1
        usage["daySessions"] = int(usage.get("daySessions", 0)) + 1
        usage["hourSessions"] = int(usage.get("hourSessions", 0)) + 1
        usage["activeSession"] = {"sessionId": session_id, "expiresAt": expires_at.isoformat()}
        _save_usage(path, usage)
        return {
            "mode": "PHOTOREALISTIC",
            "googleMapsApiKey": api_key,
            "styleUrl": os.getenv("MAP_STYLE_URL", "https://tiles.openfreemap.org/styles/liberty").strip() or "https://tiles.openfreemap.org/styles/liberty",
            "sessionId": session_id,
            "expiresAt": expires_at.isoformat().replace("+00:00", "Z"),
            "reused": False,
            "reason": "New guarded Google session allocated",
            "limits": limits,
        }
