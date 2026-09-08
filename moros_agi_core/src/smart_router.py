"""Dual-local Ollama routing with multi-tier cloud failover."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from moros_agi_core.config.settings import ACTIVE_HW_PROFILE, Settings, get_settings
from moros_agi_core.src.utils import sanitize_user_text, with_backoff

CODE_HINT = re.compile(
    r"(```|def |class |import |from |select |console\.log|\{[\s\S]*\}|"
    r"\b(json|debug|refactor|algorithm|compile|typescript|python)\b|"
    r"[\d]+\s*[\+\-\*\/]\s*[\d]+)",
    re.I,
)


class TaskKind(str, Enum):
    PERSONA = "persona"
    CODE = "code"


class ProviderName(str, Enum):
    OLLAMA = "ollama"
    HUGGINGFACE = "huggingface"
    GEMINI = "gemini"
    HIVE = "hive"
    OPENROUTER = "openrouter"


@dataclass(slots=True)
class ChatMessage:
    role: str
    content: str


@dataclass(slots=True)
class RouteResult:
    text: str
    provider: ProviderName
    model: str
    task: TaskKind
    reasoning_details: dict[str, Any] | None = None
    fallback_path: list[str] = field(default_factory=list)


class TaskClassifier:
    """Send code/math/JSON to Qwen; everything else to Llama persona."""

    def classify(self, prompt: str) -> TaskKind:
        text = prompt or ""
        if CODE_HINT.search(text):
            return TaskKind.CODE
        if len(text) > 1800:
            return TaskKind.CODE
        return TaskKind.PERSONA


class ProviderError(RuntimeError):
    def __init__(self, provider: str, message: str, status: int | None = None) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.status = status


class SmartRouter:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.classifier = TaskClassifier()
        self.num_ctx = ACTIVE_HW_PROFILE.num_ctx
        self._client = httpx.AsyncClient(
            timeout=self.settings.request_timeout_sec,
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def local_model_for(self, kind: TaskKind) -> str:
        if kind is TaskKind.CODE:
            return self.settings.ollama_code_model
        return self.settings.ollama_persona_model

    async def complete(
        self,
        prompt: str,
        history: list[ChatMessage] | None = None,
        system: str | None = None,
    ) -> RouteResult:
        clean = sanitize_user_text(prompt)
        task = self.classifier.classify(clean)
        messages = self._messages(clean, history, system)
        path: list[str] = []
        errors: list[str] = []

        steps: list[tuple[str, Any]] = [
            ("ollama", lambda: self._ollama(messages, self.local_model_for(task), task)),
            ("huggingface", lambda: self._huggingface(messages, task)),
            ("gemini", lambda: self._gemini(messages, task)),
            ("hive", lambda: self._hive(messages, task)),
            ("openrouter", lambda: self._openrouter(messages, task)),
        ]
        for name, fn in steps:
            path.append(name)
            try:
                result = await fn()
                result.fallback_path = path
                return result
            except Exception as exc:
                errors.append(f"{name}: {exc}")
                continue
        raise ProviderError("router", "all providers failed: " + " | ".join(errors))

    def _messages(
        self,
        prompt: str,
        history: list[ChatMessage] | None,
        system: str | None,
    ) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        if system:
            out.append({"role": "system", "content": system})
        for item in history or []:
            if item.role in {"user", "assistant", "system"} and item.content:
                out.append({"role": item.role, "content": item.content[:4000]})
        out.append({"role": "user", "content": prompt})
        return out[-24:]

    async def _ollama(
        self, messages: list[dict[str, str]], model: str, task: TaskKind
    ) -> RouteResult:
        host = self.settings.ollama_host.rstrip("/")

        async def _call() -> httpx.Response:
            return await self._client.post(
                f"{host}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "keep_alive": self.settings.ollama_keep_alive,
                    "options": {"num_ctx": self.num_ctx},
                },
            )

        res = await with_backoff(_call, attempts=2, retry_on=(httpx.TransportError,))
        if res.status_code >= 400:
            raise ProviderError("ollama", res.text[:300], res.status_code)
        data = res.json()
        text = ((data.get("message") or {}).get("content")) or data.get("response") or ""
        if not text.strip():
            raise ProviderError("ollama", "empty completion")
        return RouteResult(text=text.strip(), provider=ProviderName.OLLAMA, model=model, task=task)

    async def _huggingface(self, messages: list[dict[str, str]], task: TaskKind) -> RouteResult:
        key = self.settings.secret(self.settings.huggingface_api_key)
        if not key:
            raise ProviderError("huggingface", "HUGGINGFACE_API_KEY missing")
        prompt = self._flatten(messages)
        url = f"https://api-inference.huggingface.co/models/{self.settings.hf_model}"

        async def _call() -> httpx.Response:
            return await self._client.post(
                url,
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "inputs": prompt,
                    "parameters": {"max_new_tokens": 512, "return_full_text": False},
                },
            )

        res = await with_backoff(_call, attempts=3, retry_on=(httpx.TransportError,))
        if res.status_code in {429, 503, 500, 502, 504}:
            await with_backoff(lambda: _sleep_ok(), attempts=2)
            res = await _call()
        if res.status_code >= 400:
            raise ProviderError("huggingface", res.text[:300], res.status_code)
        payload = res.json()
        text = _hf_text(payload)
        if not text:
            raise ProviderError("huggingface", "empty completion")
        return RouteResult(
            text=text,
            provider=ProviderName.HUGGINGFACE,
            model=self.settings.hf_model,
            task=task,
        )

    async def _gemini(self, messages: list[dict[str, str]], task: TaskKind) -> RouteResult:
        key = self.settings.secret(self.settings.gemini_api_key)
        if not key:
            raise ProviderError("gemini", "GEMINI_API_KEY missing")
        contents = []
        for msg in messages:
            role = "user" if msg["role"] != "assistant" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        model = self.settings.gemini_model
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        res = await self._client.post(url, params={"key": key}, json={"contents": contents})
        if res.status_code >= 400:
            pro = self.settings.gemini_model_pro
            url_pro = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{pro}:generateContent"
            )
            res = await self._client.post(url_pro, params={"key": key}, json={"contents": contents})
            model = pro
        if res.status_code >= 400:
            raise ProviderError("gemini", res.text[:300], res.status_code)
        data = res.json()
        cands = data.get("candidates") or []
        parts = (((cands[0] or {}).get("content") or {}).get("parts") or []) if cands else []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
        if not text:
            raise ProviderError("gemini", "empty completion")
        return RouteResult(text=text, provider=ProviderName.GEMINI, model=model, task=task)

    async def _hive(self, messages: list[dict[str, str]], task: TaskKind) -> RouteResult:
        key = self.settings.secret(self.settings.hive_api_key)
        if not key:
            raise ProviderError("hive", "HIVE_API_KEY missing")
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        if self.settings.hive_access_id:
            headers["X-Access-Id"] = self.settings.hive_access_id
        url = self.settings.hive_base_url.rstrip("/") + "/v1/chat/completions"
        res = await self._client.post(
            url,
            headers=headers,
            json={"model": self.settings.hive_model, "messages": messages, "stream": False},
        )
        if res.status_code >= 400:
            raise ProviderError("hive", res.text[:300], res.status_code)
        data = res.json()
        text = (
            (((data.get("choices") or [{}])[0].get("message") or {}).get("content"))
            or data.get("output")
            or ""
        )
        if not str(text).strip():
            raise ProviderError("hive", "empty completion")
        return RouteResult(
            text=str(text).strip(),
            provider=ProviderName.HIVE,
            model=self.settings.hive_model,
            task=task,
        )

    async def _openrouter(self, messages: list[dict[str, str]], task: TaskKind) -> RouteResult:
        key = self.settings.secret(self.settings.openrouter_api_key)
        alt = self.settings.secret(self.settings.openrouter_api_key_secondary)
        if not key and not alt:
            raise ProviderError("openrouter", "OPENROUTER_API_KEY missing")
        models = [self.settings.openrouter_model, self.settings.openrouter_model_secondary]
        keys = [k for k in (key, alt) if k]
        last_err = "no attempt"
        for token in keys:
            for model in models:
                res = await self._client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/taslimabintenuruzzaman-star/taief-repo",
                        "X-Title": "MOROS AGI",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "reasoning": {"effort": "medium"},
                    },
                )
                if res.status_code >= 400:
                    last_err = res.text[:300]
                    continue
                data = res.json()
                choice = (data.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                text = (message.get("content") or "").strip()
                if not text:
                    last_err = "empty completion"
                    continue
                details = {
                    "reasoning": message.get("reasoning"),
                    "reasoning_details": data.get("reasoning_details") or message.get("reasoning_details"),
                    "usage": data.get("usage"),
                }
                return RouteResult(
                    text=text,
                    provider=ProviderName.OPENROUTER,
                    model=model,
                    task=task,
                    reasoning_details=details,
                )
        raise ProviderError("openrouter", last_err)

    @staticmethod
    def _flatten(messages: list[dict[str, str]]) -> str:
        return "\n".join(f"{m['role']}: {m['content']}" for m in messages)[-6000:]


def _hf_text(payload: Any) -> str:
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            return str(first.get("generated_text") or first.get("summary_text") or "").strip()
    if isinstance(payload, dict):
        return str(payload.get("generated_text") or payload.get("error") or "").strip()
    return ""


async def _sleep_ok() -> None:
    return None
