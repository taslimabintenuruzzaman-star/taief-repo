"""Optional cloud speech-to-text. Keys come from environment only."""

from __future__ import annotations

import base64
from typing import Any

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
    gemini = s.secret(s.gemini_api_key)
    groq = s.secret(s.groq_api_key)
    hf = s.secret(s.huggingface_api_key)
    errors: list[str] = []
    if gemini:
        try:
            text = await _gemini_stt(audio, filename, gemini, s)
            if text:
                return {"text": text, "engine": "gemini"}
            errors.append("gemini: empty")
        except Exception as exc:
            errors.append(f"gemini: {exc}"[:180])
    if groq:
        try:
            text = await _groq_whisper(audio, filename, groq)
            if text:
                return {"text": text, "engine": "groq-whisper"}
        except Exception as exc:
            errors.append(f"groq: {exc}"[:180])
    if hf:
        try:
            text = await _hf_whisper(audio, hf)
            if text:
                return {"text": text, "engine": "hf-whisper"}
        except Exception as exc:
            errors.append(f"hf: {exc}"[:180])
    return {
        "text": "",
        "engine": "none",
        "error": (
            " ".join(errors)
            or "No STT path. Use the MIC WINDOW (Chrome speech) or type."
        ),
    }


def _audio_mime(filename: str) -> str:
    name = (filename or "").lower()
    if name.endswith(".wav"):
        return "audio/wav"
    if name.endswith(".mp3"):
        return "audio/mp3"
    if name.endswith(".ogg"):
        return "audio/ogg"
    if name.endswith(".m4a"):
        return "audio/mp4"
    return "audio/webm"


async def _gemini_stt(audio: bytes, filename: str, key: str, settings: Any) -> str:
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Transcribe this audio. Return only the spoken words, "
                            "no quotes or extra commentary. Keep Bangla in Bangla."
                        )
                    },
                    {
                        "inline_data": {
                            "mime_type": _audio_mime(filename),
                            "data": base64.b64encode(audio).decode("ascii"),
                        }
                    },
                ]
            }
        ]
    }
    models = [
        getattr(settings, "gemini_model", "") or "gemini-2.0-flash",
        getattr(settings, "gemini_model_pro", "") or "gemini-1.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ]
    last = "no attempt"
    seen: set[str] = set()
    for model in models:
        if not model or model in seen:
            continue
        seen.add(model)
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                res = await client.post(url, params={"key": key}, json=payload)
        except httpx.HTTPError:
            try:
                async with httpx.AsyncClient(
                    timeout=60.0, follow_redirects=True, verify=False
                ) as client:
                    res = await client.post(url, params={"key": key}, json=payload)
            except httpx.HTTPError as exc:
                last = str(exc)
                continue
        if res.status_code >= 400:
            last = res.text[:240]
            continue
        data = res.json()
        cands = data.get("candidates") or []
        parts = (((cands[0] or {}).get("content") or {}).get("parts") or []) if cands else []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
        if text:
            return text
        last = "empty completion"
    raise RuntimeError(last)


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
