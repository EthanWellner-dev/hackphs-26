import json

from app.services.map_guard import acquire_map_session


def test_map_guard_allocates_once_and_reuses_session(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_PHOTOREALISTIC_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_MAP_USAGE_PATH", str(tmp_path / "usage.json"))
    monkeypatch.setenv("GOOGLE_PHOTOREALISTIC_MONTHLY_SESSION_LIMIT", "1")
    monkeypatch.setenv("GOOGLE_PHOTOREALISTIC_DAILY_SESSION_LIMIT", "1")
    monkeypatch.setenv("GOOGLE_PHOTOREALISTIC_HOURLY_SESSION_LIMIT", "1")

    first = acquire_map_session()
    second = acquire_map_session()

    assert first["mode"] == "PHOTOREALISTIC"
    assert first["reused"] is False
    assert second["reused"] is True
    assert second["sessionId"] == first["sessionId"]
    assert json.loads((tmp_path / "usage.json").read_text())["monthSessions"] == 1


def test_map_guard_falls_back_when_quota_is_exhausted(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_PHOTOREALISTIC_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_MAP_USAGE_PATH", str(tmp_path / "usage.json"))
    monkeypatch.setenv("GOOGLE_PHOTOREALISTIC_MONTHLY_SESSION_LIMIT", "0")

    result = acquire_map_session()

    assert result["mode"] == "OPEN_3D"
    assert result["googleMapsApiKey"] is None
    assert "limit" in result["reason"]
