"""Pydantic-validated facial telemetry over WebSocket."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from pydantic import BaseModel, Field

from moros_agi_core.config.settings import get_settings

PHONEME_MAP = {
    "a": "A",
    "e": "E",
    "i": "I",
    "o": "O",
    "u": "U",
    "m": "M",
    "b": "M",
    "p": "M",
    "f": "F",
    "v": "F",
}


class Euler(BaseModel):
    pitch: float = 0.0
    yaw: float = 0.0
    roll: float = 0.0


class FaceTelemetry(BaseModel):
    eyebrow_twitch: float = Field(default=0.08, ge=0.0, le=1.0)
    eye_unblink_stare: float = Field(default=0.72, ge=0.0, le=1.0)
    asymmetrical_smirk: float = Field(default=0.18, ge=0.0, le=1.0)
    head: Euler = Field(default_factory=Euler)
    lip_sync_phonemes: list[str] = Field(default_factory=list)
    tag: str | None = None


def phonemes_for(text: str) -> list[str]:
    out: list[str] = []
    for ch in (text or "").lower():
        if ch in PHONEME_MAP:
            out.append(PHONEME_MAP[ch])
    return out[:48]


def telemetry_from(text: str, tags: list[str] | None = None) -> FaceTelemetry:
    tags = [t.lower() for t in (tags or [])]
    smirk = 0.42 if "dark chuckle" in tags else 0.16
    stare = 0.9 if "whisper" in tags else 0.7
    roll = -14.0 if "glitch" in tags else (-6.0 if "sigh" in tags else 3.0)
    return FaceTelemetry(
        eyebrow_twitch=0.22 if "glitch" in tags else 0.09,
        eye_unblink_stare=stare,
        asymmetrical_smirk=smirk,
        head=Euler(pitch=2.0, yaw=4.0, roll=roll),
        lip_sync_phonemes=phonemes_for(text),
        tag=tags[0] if tags else None,
    )


class AvatarSync:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.queue: asyncio.Queue[FaceTelemetry] = asyncio.Queue()
        self._clients: set[Any] = set()
        self._server: Any = None

    async def publish(self, face: FaceTelemetry) -> None:
        payload = face.model_dump()
        FaceTelemetry.model_validate(payload)
        await self.queue.put(face)
        dead: list[Any] = []
        blob = json.dumps(payload)
        for ws in list(self._clients):
            try:
                await ws.send(blob)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)

    async def start(self) -> None:
        import websockets

        async def handler(ws: Any) -> None:
            self._clients.add(ws)
            try:
                async for _ in ws:
                    pass
            finally:
                self._clients.discard(ws)

        self._server = await websockets.serve(
            handler,
            self.settings.ws_host,
            self.settings.ws_port,
            ping_interval=20,
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._clients.clear()
