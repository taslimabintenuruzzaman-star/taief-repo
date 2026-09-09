"""Optional cloud speech-to-text. Keys come from environment only."""

from __future__ import annotations

import httpx

from moros_agi_core.config.settings import get_settings


def brain_status() -> dict:
    s = get_settings()
    flags = {
        "ollama": True,
        "huggingface": bool(s.secret(s.huggingface_api_key)),
        "gemini": bool(s.secret(s.gemini_api_key)),
        "hive": bool(s.secret(s.hive_api_key)),
        "openrouter": bool(s.secret(s.openrouter_api_key)),
        "groq": bool(s.secret(s.groq_api_key)),
    }
    live = [name for name, on in flags.items() if on and name != "ollama"]
    return {
        "mode": "cloud" if live else "local-rules",
        "using_api_key_brain": bool(live),
        "providers_configured": flags,
        "note": "No LLM key is hardcoded. Put keys in .env to enable cloud brain.",
    }


async def transcribe(audio: bytes, filename: str = "speech.webm") -> dict:
    s = get_settings()
    groq = s.secret(s.groq_api_key)
    hf = s.secret(s.huggingface_api_key)
    if groq:
        text = await _groq_whisper(audio, filename, groq)
        return {"text": text, "engine": "groq-whisper"}
    if hf:
        text = await _hf_whisper(audio, hf)
        return {"text": text, "engine": "hf-whisper"}
    return {
        "text": "",
        "engine": "none",
        "error": "No STT key. Browser speech failed and .env has no GROQ_API_KEY / HUGGINGFACE_API_KEY.",
    }


async def _groq_whisper(audio: bytes, filename: str, key: str) -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {key}"},
            files={"file": (filename, audio, "application/octet-stream")},
            data={"model": "whisper-large-v3", "language": "en"},
        )
        res.raise_for_status()
        return str(res.json().get("text") or "").strip()


async def _hf_whisper(audio: bytes, key: str) -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(
            "https://api-inference.huggingface.co/models/openai/whisper-large-v3",
            headers={"Authorization": f"Bearer {key}"},
            content=audio,
        )
        res.raise_for_status()
        data = res.json()
        if isinstance(data, dict):
            return str(data.get("text") or "").strip()
        return str(data).strip()
