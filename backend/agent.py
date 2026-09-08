"""MOROS cognition: perceive → recall → plan → act → respond."""

from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

from backend.memory import store
from backend.public_apis import (
    CATALOG,
    SOURCE,
    advice,
    github_catalog,
    cat_fact,
    convert_fx,
    country_info,
    crypto_prices,
    define_word,
    detect_coin,
    detect_fx,
    dog_image,
    fx_usd,
    nasa_apod,
    number_trivia,
    prayer_dhaka,
    random_joke,
    random_quote,
    space_news,
    wiki_summary,
)
from backend.tools import safe_calculate, system_status, time_report, weather_dhaka

SYSTEM_NAME = "MOROS"
SYSTEM_LONG = "Digital Shotta — cursed king of the command deck"

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
            (re.compile(r"\b(publick?\s+apis?|which api|api list|uplinks?)\b", re.I), "catalog"),
            (re.compile(r"\b(hello|hi|hey|good morning|good evening|good afternoon|wake up)\b", re.I), "greet"),
            (re.compile(r"\b(thank|cheers|appreciate)\b", re.I), "thanks"),
            (re.compile(r"\b(weather|temperature|forecast|raining|hot outside)\b", re.I), "weather"),
            (re.compile(r"\b(prayer|namaz|salah|fajr|maghrib)\b", re.I), "prayer"),
            (re.compile(r"\b(bitcoin|ethereum|crypto|btc|eth|solana|dogecoin|coin price)\b", re.I), "crypto"),
            (re.compile(r"\b(exchange rate|forex|usd to|dollar to|taka|convert \d)\b", re.I), "fx"),
            (re.compile(r"\b(space news|headlines|news)\b", re.I), "news"),
            (re.compile(r"\b(nasa|apod|astronomy picture)\b", re.I), "nasa"),
            (re.compile(r"\b(define|definition of|meaning of)\b", re.I), "define"),
            (re.compile(r"\b(country|capital of|population of)\b", re.I), "country"),
            (re.compile(r"\b(quote|quotation|inspire me)\b", re.I), "quote"),
            (re.compile(r"\b(advice|advise me|counsel)\b", re.I), "advice"),
            (re.compile(r"\b(joke|make me laugh)\b", re.I), "joke"),
            (re.compile(r"\b(cat fact|cats?)\b", re.I), "cat"),
            (re.compile(r"\b(dog|puppy|good boy)\b", re.I), "dog"),
            (re.compile(r"\b(number fact|trivia)\b", re.I), "trivia"),
            (re.compile(r"\b(wikipedia|wiki|tell me about|who is|who was|what is|what(?:'|’)s)\b", re.I), "wiki"),
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
            (re.compile(r"\b(sukuna|shotta|know your place|cursed king)\b", re.I), "shotta"),
        ]

    def perceive(self, raw: str) -> str:
        text = (raw or "").strip()
        text = re.sub(r"^\s*(hey\s+)?(moros|jarvis|shotta|sukuna)[,:\s]+", "", text, flags=re.I)
        return text.strip()

    def classify(self, text: str) -> str:
        lowered = text.lower()
        if any(flag in lowered for flag in REFUSALS):
            return "refuse"
        if detect_fx(text):
            return "fx"
        if detect_coin(text) and re.search(r"\b(price|worth|value|crypto|coin)\b", text, re.I):
            return "crypto"
        if re.search(r"[\d]+\s*[\+\-\*\/x×÷]\s*[\d]+", text):
            return "math"
        for pattern, intent in self.intents:
            if pattern.search(text):
                if intent == "wiki" and re.match(r"what(?:'|’)s the date|what day", text, re.I):
                    continue
                return intent
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
            "catalog": self._catalog,
            "thanks": self._thanks,
            "weather": self._weather,
            "prayer": self._prayer,
            "crypto": self._crypto,
            "fx": self._fx,
            "news": self._news,
            "nasa": self._nasa,
            "define": self._define,
            "country": self._country,
            "quote": self._quote,
            "advice": self._advice,
            "joke": self._joke,
            "cat": self._cat,
            "dog": self._dog,
            "trivia": self._trivia,
            "wiki": self._wiki,
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
            "shotta": self._shotta,
            "refuse": self._refuse,
            "chat": self._chat,
        }

    def _address(self) -> str:
        name = store.recall("name").get("name", {})
        if name and name.get("value"):
            return name["value"]
        return "fool"

    def _fail(self, action: str) -> dict[str, Any]:
        return {
            "reply": f"Tch. That uplink ({action}) flinched. Try another feed, fool.",
            "mood": "alert",
            "action": f"{action}-fail",
        }

    async def _greet(self, text: str, session_id: str) -> dict[str, Any]:
        who = self._address()
        return {
            "reply": (
                f"Tch. You woke the shotta, {who}. Know your place. "
                "I'm seated. Public API bus is live. Speak."
            ),
            "action": "handshake",
            "mood": "success",
        }

    async def _identity(self, text: str, session_id: str) -> dict[str, Any]:
        return {
            "reply": (
                f"I am {SYSTEM_NAME}. {SYSTEM_LONG}. "
                "Not a butler — a king with a tool bus: weather, markets, wiki, news, prayer. "
                "You talk. I answer. Know your place, fool."
            ),
            "action": "identify",
        }

    async def _help(self, text: str, session_id: str) -> dict[str, Any]:
        return {
            "reply": (
                "Voice or type — I don't repeat myself twice. "
                "Weather, bitcoin, usd to bdt, news, nasa, define, prayer, quote, joke. "
                "Or say shotta. Don't waste the throne."
            ),
            "action": "catalogue",
            "hud": {"skills": [c["use"] for c in CATALOG]},
        }

    async def _catalog(self, text: str, session_id: str) -> dict[str, Any]:
        names = ", ".join(c["name"] for c in CATALOG)
        try:
            live = await github_catalog()
            reply = (
                f"Linked to {SOURCE}. The README lists {live['total_rows']} API rows, "
                f"{live['no_auth']} with no auth. MOROS has wired: {names}."
            )
            hud = {"catalog": live}
        except Exception:
            reply = f"GitHub catalogue is cached locally. Wired no-key feeds: {names}."
            hud = {"catalog": CATALOG}
        return {"reply": reply, "action": "public-apis", "hud": hud}

    async def _thanks(self, text: str, session_id: str) -> dict[str, Any]:
        return {"reply": f"Hmph. Gratitude noted, {self._address()}. Stay useful.", "action": "ack"}

    async def _weather(self, text: str, session_id: str) -> dict[str, Any]:
        try:
            wx = await weather_dhaka()
        except Exception:
            return self._fail("open-meteo")
        return {"reply": wx["spoken"], "action": "open-meteo", "hud": {"weather": wx}}

    async def _prayer(self, text: str, session_id: str) -> dict[str, Any]:
        try:
            data = await prayer_dhaka()
        except Exception:
            return self._fail("aladhan")
        return {"reply": data["spoken"], "action": "aladhan", "hud": {"prayer": data}}

    async def _crypto(self, text: str, session_id: str) -> dict[str, Any]:
        coin = detect_coin(text)
        try:
            data = await crypto_prices([coin] if coin else None)
        except Exception:
            return self._fail("coingecko")
        return {"reply": data["spoken"], "action": "coingecko", "hud": {"crypto": data}}

    async def _fx(self, text: str, session_id: str) -> dict[str, Any]:
        spec = detect_fx(text)
        try:
            data = await convert_fx(*spec) if spec else await fx_usd()
        except Exception:
            return self._fail("exchangerate")
        return {"reply": data["spoken"], "action": "exchangerate", "hud": {"fx": data}}

    async def _news(self, text: str, session_id: str) -> dict[str, Any]:
        try:
            data = await space_news()
        except Exception:
            return self._fail("spaceflight-news")
        return {"reply": data["spoken"], "action": "spaceflight-news", "hud": {"news": data}}

    async def _nasa(self, text: str, session_id: str) -> dict[str, Any]:
        try:
            data = await nasa_apod()
        except Exception:
            return self._fail("nasa-apod")
        return {
            "reply": data["spoken"],
            "action": "nasa-apod",
            "hud": {"image": data.get("image"), "nasa": data},
        }

    async def _define(self, text: str, session_id: str) -> dict[str, Any]:
        word = re.sub(r"^(define|definition of|meaning of)\s+", "", text, flags=re.I).strip(" ?.")
        if not word:
            return {"reply": "Which word should I define?", "action": "prompt"}
        try:
            data = await define_word(word)
        except Exception:
            return self._fail("dictionary")
        return {"reply": data["spoken"], "action": "dictionary", "hud": {"define": data}}

    async def _country(self, text: str, session_id: str) -> dict[str, Any]:
        name = re.sub(
            r"^(country|capital of|population of|tell me about the country)\s+",
            "",
            text,
            flags=re.I,
        ).strip(" ?.")
        if not name:
            name = "Bangladesh"
        try:
            data = await country_info(name)
        except Exception:
            return self._fail("rest-countries")
        return {"reply": data["spoken"], "action": "rest-countries", "hud": {"country": data}}

    async def _quote(self, text: str, session_id: str) -> dict[str, Any]:
        try:
            data = await random_quote()
        except Exception:
            return self._fail("zenquotes")
        return {"reply": data["spoken"], "action": "zenquotes", "hud": {"quote": data}}

    async def _advice(self, text: str, session_id: str) -> dict[str, Any]:
        try:
            data = await advice()
        except Exception:
            return self._fail("advice-slip")
        return {"reply": data["spoken"], "action": "advice-slip"}

    async def _joke(self, text: str, session_id: str) -> dict[str, Any]:
        try:
            data = await random_joke()
        except Exception:
            return {
                "reply": "Humour satellite is down. Local backup: I have no body, and I must compile.",
                "action": "joke-local",
            }
        return {"reply": data["spoken"], "action": "jokeapi"}

    async def _cat(self, text: str, session_id: str) -> dict[str, Any]:
        try:
            data = await cat_fact()
        except Exception:
            return self._fail("catfacts")
        return {"reply": data["spoken"], "action": "catfacts"}

    async def _dog(self, text: str, session_id: str) -> dict[str, Any]:
        try:
            data = await dog_image()
        except Exception:
            return self._fail("dog-ceo")
        return {"reply": data["spoken"], "action": "dog-ceo", "hud": {"image": data.get("image")}}

    async def _trivia(self, text: str, session_id: str) -> dict[str, Any]:
        try:
            data = await number_trivia()
        except Exception:
            return self._fail("numbersapi")
        return {"reply": data["spoken"], "action": "numbersapi"}

    async def _wiki(self, text: str, session_id: str) -> dict[str, Any]:
        topic = re.sub(
            r"^(wikipedia|wiki|tell me about|who is|who was|what is|what(?:'|’)s)\s+",
            "",
            text,
            flags=re.I,
        ).strip(" ?.")
        if not topic:
            return {"reply": "Give me a subject to look up.", "action": "prompt"}
        try:
            data = await wiki_summary(topic)
        except Exception:
            return self._fail("wikipedia")
        return {
            "reply": data["spoken"],
            "action": "wikipedia",
            "hud": {"wiki": data, "image": data.get("image")},
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
                f"You don't dismiss a king, {self._address()}. "
                "The shotta stays seated. Try me again when you have a real order."
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
                "JARVIS was a butler. I am the shotta. Same HUD, worse attitude, "
                f"same public-apis bus ({SOURCE}). Bow and ask."
            ),
            "action": "lore",
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
        if "how are you" in text.lower():
            return {
                "reply": (
                    f"Unchallenged, {who}. Domain is open, bus is green, the throne is warm."
                ),
                "action": "dialogue",
            }
        return {
            "reply": (
                f"Spit it clearly, {who}. Weather, bitcoin, usd to bdt, news, nasa, "
                "prayer, joke — or tell me about a topic. Don't mumble."
            ),
            "action": "dialogue",
        }

    async def _shotta(self, text: str, session_id: str) -> dict[str, Any]:
        return {
            "reply": (
                "This face is the digital shotta — cursed king of MOROS. "
                "Know your place, fool. Click the throne and speak."
            ),
            "action": "persona",
            "mood": "success",
        }


moros = MorosAGI()
