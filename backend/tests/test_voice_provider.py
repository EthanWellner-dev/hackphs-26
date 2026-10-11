import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.services import voice
from app.services.voice import _safe_cache_key, synthesize_dispatch


class FakeSpeech:
    def __init__(self, chunks):
        self.chunks = chunks
        self.calls: list[dict] = []

    def convert(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self.chunks)


class FakeElevenLabs:
    speech: FakeSpeech

    def __init__(self, chunks=(b"ID3", b"fake-mp3"), error=None):
        self.error = error
        self.text_to_speech = FakeSpeech(chunks)

    def __new__(cls, *args, **kwargs):
        instance = object.__new__(cls)
        instance.api_key = kwargs.get("api_key")
        return instance


def test_elevenlabs_generates_and_caches_mp3(monkeypatch, tmp_path) -> None:
    fake_client = FakeElevenLabs()
    monkeypatch.setattr(voice, "ElevenLabs", lambda api_key: fake_client)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-eleven-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "test-voice")
    monkeypatch.setenv("AUDIO_CACHE_DIR", str(tmp_path))

    result = synthesize_dispatch("Explosion confirmed")
    output_path = tmp_path / f"{result.cache_key}.mp3"
    assert result.status == "READY"
    assert result.provider == "ELEVENLABS"
    assert result.audio_url == f"/audio-cache/{output_path.name}"
    assert output_path.read_bytes() == b"ID3fake-mp3"
    call = fake_client.text_to_speech.calls[0]
    assert call["voice_id"] == "test-voice"
    assert call["output_format"] == "mp3_44100_128"
    assert call["model_id"] == "eleven_multilingual_v2"
    assert call["text"] == "Explosion confirmed"

    cached = synthesize_dispatch("Explosion confirmed")
    assert cached.status == "READY"
    assert cached.provider == "ELEVENLABS_CACHE"
    assert len(fake_client.text_to_speech.calls) == 1


def test_elevenlabs_missing_configuration_is_text_only(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    monkeypatch.setenv("AUDIO_CACHE_DIR", str(tmp_path))

    result = synthesize_dispatch("Status update")
    assert result.status == "TEXT_ONLY"
    assert result.provider == "TEXT_FALLBACK_MISSING_CONFIG"
    assert result.audio_url is None


def test_elevenlabs_provider_failure_does_not_create_partial_cache(monkeypatch, tmp_path) -> None:
    class FailingClient:
        def __init__(self, api_key):
            self.text_to_speech = self
        def convert(self, **kwargs):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(voice, "ElevenLabs", FailingClient)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-eleven-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "test-voice")
    monkeypatch.setenv("AUDIO_CACHE_DIR", str(tmp_path))

    result = synthesize_dispatch("Provider failure")
    assert result.status == "TEXT_ONLY"
    assert result.provider == "TEXT_FALLBACK_PROVIDER_ERROR"
    assert result.audio_url is None
    assert not list(tmp_path.glob("*.mp3"))


def test_elevenlabs_empty_audio_is_text_only(monkeypatch, tmp_path) -> None:
    fake_client = FakeElevenLabs(chunks=[])
    monkeypatch.setattr(voice, "ElevenLabs", lambda api_key: fake_client)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-eleven-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "test-voice")
    monkeypatch.setenv("AUDIO_CACHE_DIR", str(tmp_path))

    result = synthesize_dispatch("Empty response")
    assert result.status == "TEXT_ONLY"
    assert result.provider == "TEXT_FALLBACK_PROVIDER_ERROR"
    assert result.audio_url is None
    assert not list(tmp_path.glob("*.mp3"))


def test_cache_key_changes_with_voice_and_text() -> None:
    assert _safe_cache_key("same", "voice-a") != _safe_cache_key("same", "voice-b")
    assert _safe_cache_key("same", "voice-a") != _safe_cache_key("different", "voice-a")
