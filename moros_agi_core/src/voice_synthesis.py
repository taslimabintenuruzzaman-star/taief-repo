"""XTTS pipeline with 0.45s micro-pauses and safe CUDA cache behaviour."""

from __future__ import annotations

import asyncio
import io
import struct
import wave
from pathlib import Path
from typing import Any

from moros_agi_core.config.settings import ACTIVE_HW_PROFILE, get_settings
from moros_agi_core.src.utils import empty_cuda_cache

MICRO_PAUSE_SEC = 0.45
FRAME_BYTES = 400


class VoiceSynthesis:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.sample_rate = self.settings.sample_rate
        self.micro_pause = float(self.settings.micro_pause_sec or MICRO_PAUSE_SEC)
        self._tts: Any = None
        self._lock = asyncio.Lock()

    def _init_xtts(self) -> Any:
        if self._tts is not None:
            return self._tts
        try:
            from TTS.api import TTS  # type: ignore

            gpu = ACTIVE_HW_PROFILE.backend == "cuda"
            self._tts = TTS(model_name=self.settings.xtts_model, gpu=gpu, progress_bar=False)
        except Exception:
            self._tts = False
        return self._tts

    def silence_pcm(self, seconds: float) -> bytes:
        n = max(0, int(self.sample_rate * seconds))
        return b"\x00\x00" * n

    def align_ratecv_frame(self, chunk: bytes, expected: int = FRAME_BYTES) -> bytes:
        """Pad or trim variable capture frames (e.g. 398 vs 400 bytes)."""
        if len(chunk) == expected:
            return chunk
        if len(chunk) > expected:
            return chunk[:expected]
        return chunk + (b"\x00" * (expected - len(chunk)))

    def apply_whisper(self, pcm: bytes, gain: float = 0.45) -> bytes:
        if len(pcm) < 2:
            return pcm
        out = bytearray()
        for i in range(0, len(pcm) - 1, 2):
            sample = struct.unpack_from("<h", pcm, i)[0]
            sample = int(sample * gain)
            sample = max(-32767, min(32767, sample))
            out.extend(struct.pack("<h", sample))
        return bytes(out)

    async def render(self, text: str, tags: list[str] | None = None) -> bytes:
        tags = tags or []
        pieces: list[bytes] = []
        if "breath" in tags or "sigh" in tags:
            pieces.append(self.silence_pcm(0.22))
        if "micro-pause" in tags or "pause" in tags:
            pieces.append(self.silence_pcm(self.micro_pause))
        spoken = await asyncio.to_thread(self._speak_blocking, text)
        if "whisper" in tags:
            spoken = self.apply_whisper(spoken)
        pieces.append(spoken)
        if "dark chuckle" in tags:
            pieces.append(self.silence_pcm(0.18))
        pcm = b"".join(pieces)
        empty_cuda_cache()
        return pcm

    def _speak_blocking(self, text: str) -> bytes:
        engine = self._init_xtts()
        if not engine:
            return self.silence_pcm(max(0.2, min(4.0, len(text) * 0.04)))
        try:
            import torch  # type: ignore

            device = "cuda" if ACTIVE_HW_PROFILE.backend == "cuda" else "cpu"
            with torch.amp.autocast(device, dtype=torch.float16 if device == "cuda" else torch.float32):
                wav = engine.tts(text=text, language="en")
        except Exception:
            try:
                wav = engine.tts(text=text, language="en")
            except Exception:
                return self.silence_pcm(0.4)
        return _float_to_pcm16(wav)

    def write_wav(self, pcm: bytes, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(self.sample_rate)
            handle.writeframes(pcm)

    def wav_bytes(self, pcm: bytes) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(self.sample_rate)
            handle.writeframes(pcm)
        return buf.getvalue()


def _float_to_pcm16(wav: Any) -> bytes:
    try:
        import numpy as np  # type: ignore

        arr = np.asarray(wav, dtype=np.float32)
        arr = np.clip(arr, -1.0, 1.0)
        return (arr * 32767.0).astype("<i2").tobytes()
    except Exception:
        if isinstance(wav, (bytes, bytearray)):
            return bytes(wav)
        return b""
