"""Shared helpers: backoff, sanitization, CUDA cache."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")

CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def sanitize_user_text(text: str, limit: int = 8000) -> str:
    cleaned = CONTROL_CHARS.sub("", text or "")
    return cleaned.strip()[:limit]


async def with_backoff(
    op: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.4,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    last: BaseException | None = None
    for i in range(attempts):
        try:
            return await op()
        except retry_on as exc:
            last = exc
            await asyncio.sleep(base_delay * (2**i))
    assert last is not None
    raise last


def empty_cuda_cache() -> None:
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        return
