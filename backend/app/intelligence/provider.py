from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings
from app.intelligence.types import ChatMessage, LlmCompletion, LlmProviderStatus


class LlmNotConfiguredError(RuntimeError):
    """Raised when LLM credentials are missing."""


class LlmRequestError(RuntimeError):
    """Raised when the upstream OpenAI-compatible API fails."""


def get_llm_provider_status() -> LlmProviderStatus:
    api_key = (settings.llm_api_key or "").strip()
    model = settings.resolved_llm_chat_model()
    if not api_key:
        return LlmProviderStatus(
            configured=False,
            provider="openai-compatible",
            base_url=settings.llm_base_url,
            model=model,
            reason="LLM_API_KEY 未配置",
        )
    return LlmProviderStatus(
        configured=True,
        provider="openai-compatible",
        base_url=settings.llm_base_url,
        model=model,
        reason=None,
    )


class OpenAICompatibleProvider:
    """Minimal OpenAI-compatible chat completions client (stdlib urllib only)."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        self.base_url = (base_url if base_url is not None else settings.llm_base_url).rstrip("/")
        self.api_key = (api_key if api_key is not None else settings.llm_api_key).strip()
        self.model = model if model is not None else settings.resolved_llm_chat_model()
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.llm_timeout_seconds
        )
        self.max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens
        self.temperature = temperature if temperature is not None else settings.llm_temperature

    def status(self) -> LlmProviderStatus:
        if not self.api_key:
            return LlmProviderStatus(
                configured=False,
                provider="openai-compatible",
                base_url=self.base_url,
                model=self.model,
                reason="LLM_API_KEY 未配置",
            )
        return LlmProviderStatus(
            configured=True,
            provider="openai-compatible",
            base_url=self.base_url,
            model=self.model,
            reason=None,
        )

    def chat(
        self,
        messages: list[ChatMessage] | list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LlmCompletion:
        status = self.status()
        if not status.configured:
            raise LlmNotConfiguredError(status.reason or "LLM 未配置")

        payload = {
            "model": self.model,
            "messages": [_normalize_message(item) for item in messages],
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
        }
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}/chat/completions",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                raw = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
            raise LlmRequestError(f"LLM HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise LlmRequestError(f"LLM 请求失败: {exc}") from exc

        return _parse_completion(raw, fallback_model=self.model)


def _normalize_message(item: ChatMessage | dict[str, str]) -> dict[str, str]:
    if isinstance(item, ChatMessage):
        return {"role": item.role, "content": item.content}
    return {"role": str(item.get("role", "user")), "content": str(item.get("content", ""))}


def _parse_completion(raw: dict[str, Any], *, fallback_model: str) -> LlmCompletion:
    choices = raw.get("choices") if isinstance(raw, dict) else None
    if not isinstance(choices, list) or not choices:
        raise LlmRequestError("LLM 响应缺少 choices")
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise LlmRequestError("LLM 响应内容为空")
    return LlmCompletion(
        content=content.strip(),
        model=str(raw.get("model") or fallback_model),
        finish_reason=str(first.get("finish_reason") or "stop"),
        raw=raw if isinstance(raw, dict) else {},
    )


def get_default_provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider()
