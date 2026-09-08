"""Short-term dialogue memory and durable operator facts."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MEMORY_FILE = DATA / "memory.json"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        DATA.mkdir(parents=True, exist_ok=True)
        self._state: dict[str, Any] = {
            "facts": {},
            "notes": [],
            "sessions": {},
        }
        self._load()

    def _load(self) -> None:
        if MEMORY_FILE.exists():
            try:
                self._state = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        self._state.setdefault("facts", {})
        self._state.setdefault("notes", [])
        self._state.setdefault("sessions", {})

    def _save(self) -> None:
        MEMORY_FILE.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def append_turn(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            session = self._state["sessions"].setdefault(
                session_id, {"history": [], "created": _utcnow()}
            )
            session["history"].append(
                {"role": role, "content": content, "ts": _utcnow()}
            )
            session["history"] = session["history"][-40:]
            self._save()

    def history(self, session_id: str) -> list[dict[str, str]]:
        with self._lock:
            return list(self._state["sessions"].get(session_id, {}).get("history", []))

    def remember(self, key: str, value: str) -> None:
        with self._lock:
            self._state["facts"][key.strip().lower()] = {
                "value": value.strip(),
                "updated": _utcnow(),
            }
            self._save()

    def recall(self, key: str | None = None) -> dict[str, Any]:
        with self._lock:
            facts = self._state["facts"]
            if key:
                item = facts.get(key.strip().lower())
                return {key: item} if item else {}
            return dict(facts)

    def add_note(self, text: str) -> dict[str, Any]:
        note = {"id": _utcnow(), "text": text.strip(), "created": _utcnow()}
        with self._lock:
            self._state["notes"].insert(0, note)
            self._state["notes"] = self._state["notes"][:50]
            self._save()
        return note

    def notes(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._state["notes"])

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._state["sessions"].pop(session_id, None)
            self._save()


store = MemoryStore()
