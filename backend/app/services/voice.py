from __future__ import annotations

import io
import hashlib
import os
import re
from pathlib import Path

try:
    from elevenlabs import ElevenLabs
except ImportError:  # Text-only fallback must work without provider extras.
    ElevenLabs = None  # type: ignore[assignment]


class VoiceResult:
    def __init__(self, status: str, cache_key: str, audio_url: str | None, provider: str):
        self.status = status
        self.cache_key = cache_key
        self.audio_url = audio_url
        self.provider = provider


def _safe_cache_key(text: str, voice_id: str) -> str:
    digest = hashlib.sha256(f"{voice_id}:{text}".encode("utf-8")).hexdigest()[:16]
    return f"dispatch-{digest}"


def synthesize_dispatch(text: str) -> VoiceResult:
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    default_cache_dir = Path(__file__).resolve().parents[3] / "frontend" / "public" / "audio-cache"
    cache_dir = Path(os.getenv("AUDIO_CACHE_DIR", str(default_cache_dir)))
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = _safe_cache_key(text, voice_id or "default")
    output_path = cache_dir / f"{cache_key}.mp3"
    if output_path.exists():
        return VoiceResult("READY", cache_key, f"/audio-cache/{output_path.name}", "ELEVENLABS_CACHE")

    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not api_key or not voice_id or ElevenLabs is None:
        return VoiceResult("TEXT_ONLY", cache_key, None, "TEXT_FALLBACK_MISSING_CONFIG")

    try:
        client = ElevenLabs(api_key=api_key)
        audio = client.text_to_speech.convert(
            voice_id=voice_id,
            output_format="mp3_44100_128",
            text=text[:500],
            model_id="eleven_multilingual_v2",
        )
        temporary_path = output_path.with_suffix(".tmp")
        byte_count = 0
        with temporary_path.open("wb") as output_file:
            for chunk in audio:
                if chunk:
                    output_file.write(chunk)
                    byte_count += len(chunk)
        if byte_count == 0:
            temporary_path.unlink(missing_ok=True)
            return VoiceResult("TEXT_ONLY", cache_key, None, "TEXT_FALLBACK_PROVIDER_ERROR")
        os.replace(temporary_path, output_path)
        return VoiceResult("READY", cache_key, f"/audio-cache/{output_path.name}", "ELEVENLABS")
    except Exception:
        return VoiceResult("TEXT_ONLY", cache_key, None, "TEXT_FALLBACK_PROVIDER_ERROR")


def transcribe_recording(data: bytes, content_type: str) -> str:
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not api_key or ElevenLabs is None:
        raise RuntimeError("ElevenLabs transcription is not configured. Use browser speech recognition in Chrome or Edge.")
    suffix = {"audio/mp4": "mp4", "audio/ogg": "ogg", "audio/wav": "wav"}.get(content_type, "webm")
    recording = io.BytesIO(data)
    recording.name = f"dispatch.{suffix}"
    try:
        client = ElevenLabs(api_key=api_key, timeout=25)
        result = client.speech_to_text.convert(file=recording, model_id="scribe_v1", language_code="eng")
        text = (result.text or "").strip()
    except Exception as error:
        raise RuntimeError("Transcription provider unavailable. Retry recording or use browser speech recognition.") from error
    if not text:
        raise RuntimeError("No speech detected. Check your microphone and try again.")
    return text[:1000]
