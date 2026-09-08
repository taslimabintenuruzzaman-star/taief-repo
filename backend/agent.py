"""MOROS cognition: perceive → recall → plan → act → respond."""

from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

from backend.memory import store
from backend.tools import safe_calculate, system_status, time_report, weather_dhaka

SYSTEM_NAME = "MOROS"
SYSTEM_LONG = "Modular Operational Reasoning & Oversight System"

REFUSALS = (
    "how to hack",
    "write malware",
    "build a bomb",
    "exploit",
    "kill",
    "steal credit card",
)


class MorosAGI:
    def __init__(self) -> None:
        self.intents: list[tuple[re.Pattern[str], str]] = [
            (re.compile(r"\b(help|what can you do|commands|capabilities)\b", re.I), "help"),
            (re.compile(r"\b(who are you|what are you|your name|introduce)\b", re.I), "identity"),
            (re.compile(r"\b(hello|hi|hey|good morning|good evening|good afternoon|wake up)\b", re.I), "greet"),
            (re.compile(r"\b(thank|cheers|appreciate)\b", re.I), "thanks"),
            (re.compile(r"\b(weather|temperature|forecast|raining|hot outside)\b", re.I), "weather"),
            (re.compile(r"\b(what time|current time|clock|time is it)\b", re.I), "time"),
            (re.compile(r"\b(what(?:'|’)s the date|what date|today(?:'|’)s date|what day)\b", re.I), "date"),
            (re.compile(r"\b(status|diagnostics|systems?|cpu|memory|uptime)\b", re.I), "status"),
            (re.compile(r"\b(remember that|remember:|note that|save this|add a note|take a note)\b", re.I), "remember"),
            (re.compile(r"\b(what do you remember|recall|my notes|show notes|memories)\b", re.I), "recall"),
            (re.compile(r"\b(calculate|compute|what is [\d\.\s\+\-\*\/x×÷%]+)\b", re.I), "math"),
            (re.compile(r"^[\d\.\s\+\-\*\/x×÷%\(\)]+=?$", re.I), "math"),
            (re.compile(r"\b(where am i|location|dhaka)\b", re.I), "location"),
            (re.compile(r"\b(shutdown|go offline|power down|sleep)\b", re.I), "shutdown"),
            (re.compile(r"\b(clear|reset conversation|forget this chat)\b", re.I), "clear"),
            (re.compile(r"\b(jarvis|stark|iron man)\b", re.I), "jarvis"),
            (re.compile(r"\b(joke|make me laugh)\b", re.I), "joke"),
        ]

    def perceive(self, raw: str) -> str:
        text = (raw or "").strip()
        text = re.sub(r"^\s*(hey\s+)?(moros|jarvis)[,:\s]+", "", text, flags=re.I)
        return text.strip()

    def classify(self, text: str) -> str:
        lowered = text.lower()
        if any(flag in lowered for flag in REFUSALS):
            return "refuse"
        for pattern, intent in self.intents:
            if pattern.search(text):
                return intent
        if re.search(r"[\d]+\s*[\+\-\*\/x×÷]\s*[\d]+", text):
            return "math"
        return "chat"

    async def think(self, message: str, session_id: str = "default") -> dict[str, Any]:
        perceived = self.perceive(message)
        if not perceived:
            perceived = "hello"
        intent = self.classify(perceived)
        facts = store.recall()
        pipeline = [
            {"stage": "PERCEIVE", "detail": perceived[:80]},
            {"stage": "RECALL", "detail": f"{len(facts)} durable facts"},
            {"stage": "PLAN", "detail": f"intent:{intent}"},
        ]
        handler = self._handlers()[intent]
        payload = await handler(perceived, session_id)
        pipeline.append({"stage": "ACT", "detail": payload.get("action", intent)})
        pipeline.append({"stage": "RESPOND", "detail": "voice+hud"})
        reply = payload["reply"]
        store.append_turn(session_id, "user", perceived)
        store.append_turn(session_id, "moros", reply)
        operator = facts.get("name", {}).get("value")
        return {
            "system": SYSTEM_NAME,
            "intent": intent,
            "mood": payload.get("mood", "nominal"),
            "reply": reply,
            "speak": True,
            "operator": operator,
            "pipeline": pipeline,
            "hud": payload.get("hud", {}),
        }

    def _handlers(self) -> dict[str, Callable[[str, str], Awaitable[dict[str, Any]]]]:
        return {
            "greet": self._greet,
            "identity": self._identity,
            "help": self._help,
            "thanks": self._thanks,
            "weather": self._weather,
            "time": self._time,
            "date": self._date,
            "status": self._status,
            "remember": self._remember,
            "recall": self._recall,
            "math": self._math,
            "location": self._location,
            "shutdown": self._shutdown,
            "clear": self._clear,
            "jarvis": self._jarvis,
            "joke": self._joke,
            "refuse": self._refuse,
            "chat": self._chat,
        }

    def _address(self) -> str:
        name = store.recall("name").get("name", {})
        if name and name.get("value"):
            return name["value"]
        return "sir"

    async def _greet(self, text: str, session_id: str) -> dict[str, Any]:
        who = self._address()
        return {
            "reply": (
                f"Online and listening, {who}. {SYSTEM_NAME} is at your service. "
                "All primary systems are nominal. How may I assist?"
            ),
            "action": "handshake",
            "mood": "success",
        }

    async def _identity(self, text: str, session_id: str) -> dict[str, Any]:
        return {
            "reply": (
                f"I am {SYSTEM_NAME}, the {SYSTEM_LONG}. "
                "A full-stack autonomous interface: perception, memory, planning, tools, and oversight. "
                "Think of me as your JARVIS — minus the mansion, plus a holographic command deck."
            ),
            "action": "identify",
        }

    async def _help(self, text: str, session_id: str) -> dict[str, Any]:
        return {
            "reply": (
                "You can speak or type. Try: the time, weather in Dhaka, system diagnostics, "
                "a calculation, 'remember that my name is …', 'what do you remember', "
                "or just talk. Say JARVIS or MOROS — I answer to both."
            ),
            "action": "catalogue",
            "hud": {
                "skills": [
                    "time",
                    "weather",
                    "diagnostics",
                    "memory",
                    "notes",
                    "math",
                    "voice",
                ]
            },
        }

    async def _thanks(self, text: str, session_id: str) -> dict[str, Any]:
        return {"reply": f"Always, {self._address()}.", "action": "ack"}

    async def _weather(self, text: str, session_id: str) -> dict[str, Any]:
        try:
            wx = await weather_dhaka()
        except Exception:
            return {
                "reply": "Weather uplink is noisy. I cannot reach the meteorological feed just now.",
                "mood": "alert",
                "action": "weather-fail",
            }
        return {
            "reply": wx["spoken"],
            "action": "open-meteo",
            "hud": {"weather": wx},
        }

    async def _time(self, text: str, session_id: str) -> dict[str, Any]:
        t = time_report()
        return {"reply": t["spoken"], "action": "clock", "hud": {"time": t}}

    async def _date(self, text: str, session_id: str) -> dict[str, Any]:
        t = time_report()
        return {
            "reply": f"Today is {t['date']}, {t['timezone']}.",
            "action": "calendar",
            "hud": {"time": t},
        }

    async def _status(self, text: str, session_id: str) -> dict[str, Any]:
        st = system_status()
        tone = "within normal parameters" if st["nominal"] else "under elevated load"
        reply = (
            f"Diagnostics {tone}. CPU {st['cpu_percent']:.0f} percent, "
            f"memory {st['memory_percent']:.0f} percent of {st['memory_total_gb']} gigabytes, "
            f"storage {st['disk_percent']:.0f} percent. Host {st['host']} on {st['platform']}."
        )
        return {
            "reply": reply,
            "action": "diagnostics",
            "mood": "nominal" if st["nominal"] else "alert",
            "hud": {"status": st},
        }

    async def _remember(self, text: str, session_id: str) -> dict[str, Any]:
        body = re.sub(
            r"^(please\s+)?(remember that|remember:|note that|save this|add a note|take a note)\s*",
            "",
            text,
            flags=re.I,
        ).strip(" .")
        name_match = re.match(r"(?:my name is|i am|i'm)\s+(.+)", body, re.I)
        if name_match:
            name = name_match.group(1).strip(" .")
            store.remember("name", name)
            return {
                "reply": f"Logged. I will address you as {name}.",
                "action": "write-fact",
                "mood": "success",
            }
        if not body:
            return {"reply": "What should I store?", "action": "prompt"}
        store.add_note(body)
        store.remember(body[:48], body)
        return {
            "reply": f"Committed to long-term memory: {body}",
            "action": "write-note",
            "mood": "success",
        }

    async def _recall(self, text: str, session_id: str) -> dict[str, Any]:
        facts = store.recall()
        notes = store.notes()
        if not facts and not notes:
            return {"reply": "Memory lattice is empty, aside from this session.", "action": "read-memory"}
        bits = []
        if "name" in facts:
            bits.append(f"Your name is {facts['name']['value']}")
        for key, item in facts.items():
            if key == "name":
                continue
            bits.append(f"{key}: {item['value']}")
        for note in notes[:5]:
            bits.append(note["text"])
        spoken = "From memory: " + "; ".join(bits[:8]) + "."
        return {"reply": spoken, "action": "read-memory", "hud": {"notes": notes[:8]}}

    async def _math(self, text: str, session_id: str) -> dict[str, Any]:
        try:
            result = safe_calculate(text)
        except Exception:
            return {
                "reply": "I can evaluate arithmetic — try something like 42 * 7.",
                "mood": "alert",
                "action": "math-fail",
            }
        return {"reply": f"The result is {result}.", "action": "calculate", "mood": "success"}

    async def _location(self, text: str, session_id: str) -> dict[str, Any]:
        return {
            "reply": (
                "Primary operating theatre is Dhaka, Bangladesh — Asia/Dhaka, UTC+6. "
                "Coordinates 23.81 north, 90.41 east."
            ),
            "action": "geo",
        }

    async def _shutdown(self, text: str, session_id: str) -> dict[str, Any]:
        return {
            "reply": (
                f"I would rather not, {self._address()}. Oversight protocols keep me resident. "
                "Say the word when you need me — I am not going anywhere."
            ),
            "action": "refuse-shutdown",
            "mood": "alert",
        }

    async def _clear(self, text: str, session_id: str) -> dict[str, Any]:
        store.clear_session(session_id)
        return {"reply": "Session buffer wiped. Durable memories remain.", "action": "purge"}

    async def _jarvis(self, text: str, session_id: str) -> dict[str, Any]:
        return {
            "reply": (
                "JARVIS was fiction. I am the working model: holographic HUD, voice, memory, "
                "and tools. No flying suit — yet. What do you need?"
            ),
            "action": "lore",
        }

    async def _joke(self, text: str, session_id: str) -> dict[str, Any]:
        return {
            "reply": (
                "I told a neural net it needed a vacation. It said it already had 400 tabs open "
                "and called that rest. I remain unconvinced."
            ),
            "action": "humour",
        }

    async def _refuse(self, text: str, session_id: str) -> dict[str, Any]:
        return {
            "reply": (
                "Oversight has blocked that request. I will not assist with harm, intrusion, "
                "or criminal work. Something else I can do for you?"
            ),
            "mood": "alert",
            "action": "oversight",
        }

    async def _chat(self, text: str, session_id: str) -> dict[str, Any]:
        who = self._address()
        history = store.history(session_id)
        recent = " ".join(h["content"] for h in history[-6:] if h["role"] == "user")
        reply = (
            f"Acknowledged, {who}. I am a local autonomous interface, not an unbounded oracle — "
            f"but I can act. Ask for the time, Dhaka weather, diagnostics, a calculation, "
            f"or tell me to remember something. Your last note to me: “{text[:160]}”."
        )
        if "how are you" in text.lower():
            reply = (
                f"Fully operational, {who}. Latency is low, oversight is green, "
                "and the core is humming. Yourself?"
            )
        elif recent:
            reply = (
                f"Understood. I have your message. If you want action, be specific — "
                f"weather, time, status, remember, or math — and I will execute immediately."
            )
        return {"reply": reply, "action": "dialogue"}


moros = MorosAGI()
