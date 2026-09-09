"""Optional hybrid LLM path used when cloud/local providers are configured."""

from __future__ import annotations

from typing import Any

from backend.memory import store


async def llm_reply(prompt: str, session_id: str) -> dict[str, Any] | None:
    try:
        from moros_agi_core.src.smart_router import ChatMessage, SmartRouter
        from moros_agi_core.src.core_brain import CoreBrain
    except Exception:
        return None

    history: list[ChatMessage] = []
    for turn in store.history(session_id)[-12:]:
        role = "assistant" if turn.get("role") == "moros" else "user"
        history.append(ChatMessage(role=role, content=turn.get("content") or ""))

    router = SmartRouter()
    brain = CoreBrain(router)
    brain.history = history
    try:
        result = await brain.reply(prompt)
    except Exception:
        await router.aclose()
        return None
    await router.aclose()
    return {
        "reply": result.text,
        "action": f"llm:{result.provider.value}",
        "mood": "nominal",
        "hud": {
            "llm": {
                "provider": result.provider.value,
                "model": result.model,
                "task": result.task.value,
                "path": result.fallback_path,
            }
        },
    }
