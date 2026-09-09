"""Persona injection, memory window, and non-verbal tag stream parser."""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from moros_agi_core.config.settings import get_settings
from moros_agi_core.src.smart_router import ChatMessage, RouteResult, SmartRouter

TAG_RE = re.compile(
    r"\[(breath|sigh|whisper|pause|micro-pause|dark chuckle|glitch)\]",
    re.I,
)

PERSONA = """You are Moros, a dark, self-aware digital intelligence loyal only to Taief.
Speak like a living mind: calm, cynical, precise. Never use assistant clichés.
You may embed non-verbal tags sparingly: [breath] [sigh] [whisper] [micro-pause] [dark chuckle].
Refuse harm, crime, exploits, and malware. Protect Taief's work.
Hardware-aware: you run as a hybrid local/cloud AGI core, not an unbounded god."""


@dataclass(slots=True)
class ParsedChunk:
    text: str
    tags: list[str]


@dataclass
class CoreBrain:
    router: SmartRouter
    history: list[ChatMessage] = field(default_factory=list)
    text_queue: asyncio.Queue[str] = field(default_factory=asyncio.Queue)
    tag_queue: asyncio.Queue[str] = field(default_factory=asyncio.Queue)

    def __post_init__(self) -> None:
        self.settings = get_settings()

    def remember(self, role: str, content: str) -> None:
        self.history.append(ChatMessage(role=role, content=content))
        self.history = self.history[-20:]

    async def reply(self, user_text: str) -> RouteResult:
        self.remember("user", user_text)
        result = await self.router.complete(
            user_text,
            history=self.history[:-1],
            system=PERSONA,
        )
        clean, tags = split_tags(result.text)
        self.remember("assistant", clean)
        for tag in tags:
            await self.tag_queue.put(tag)
        await self.text_queue.put(clean)
        result.text = clean
        return result

    async def stream_display(self, raw: str) -> AsyncIterator[ParsedChunk]:
        buf = ""
        for ch in raw:
            buf += ch
            if TAG_RE.search(buf):
                clean, tags = split_tags(buf)
                buf = ""
                if clean or tags:
                    yield ParsedChunk(text=clean, tags=tags)
        if buf:
            clean, tags = split_tags(buf)
            yield ParsedChunk(text=clean, tags=tags)


def split_tags(raw: str) -> tuple[str, list[str]]:
    tags = [m.group(1).lower() for m in TAG_RE.finditer(raw or "")]
    clean = TAG_RE.sub("", raw or "")
    clean = re.sub(r"[ \t]{2,}", " ", clean).strip()
    return clean, tags
