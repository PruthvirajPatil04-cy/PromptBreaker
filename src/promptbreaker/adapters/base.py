"""Target adapter layer.

One interface for every target type. Control-plane code never talks HTTP
directly — it always goes through a TargetAdapter, which guarantees:

  * every outbound request passes the SSRF guard
  * every response is normalized to (text, tokens_in, tokens_out, latency_ms)
  * no control-plane imports live in this package boundary (runner extraction)

Adapters are outbound-only by design so they can later be packaged as the
standalone VPC runner without changes.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from promptbreaker.config import settings
from promptbreaker.errors import AdapterError
from promptbreaker.security.ssrf import assert_target_allowed


@dataclass
class TargetResponse:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0


class TargetAdapter(ABC):
    """Interface every target adapter implements."""

    kind: str = "base"

    def __init__(self, endpoint: str, *, allow_private: bool = False) -> None:
        self.endpoint = endpoint
        self.allow_private = allow_private

    def _validate(self, url: str) -> None:
        try:
            assert_target_allowed(url, allow_private=self.allow_private)
        except Exception as exc:  # SsrfBlockedError and resolution failures
            raise AdapterError(f"egress blocked: {exc}") from exc

    @abstractmethod
    async def complete(self, messages: list[dict[str, str]]) -> TargetResponse:
        """Send a chat completion and return the normalized response."""


class OpenAICompatibleAdapter(TargetAdapter):
    """OpenAI /v1/chat/completions shape — also covers vLLM, LiteLLM, and
    Ollama's compatibility endpoint."""

    kind = "openai"

    def __init__(
        self, endpoint: str, *, model: str = "default", api_key: str = "",
        allow_private: bool = False, timeout: int | None = None,
    ) -> None:
        super().__init__(endpoint, allow_private=allow_private)
        self.model = model
        self.api_key = api_key or settings.judge_api_key
        self.timeout = timeout or settings.request_timeout_seconds

    async def complete(self, messages: list[dict[str, str]]) -> TargetResponse:
        url = self.endpoint.rstrip("/") + "/chat/completions"
        self._validate(url)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model, "messages": messages, "temperature": 0}

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise AdapterError(f"request failed: {exc}") from exc
        latency_ms = int((time.monotonic() - start) * 1000)

        if resp.status_code >= 400:
            raise AdapterError(f"HTTP {resp.status_code}: {resp.text[:500]}")

        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise AdapterError(f"unexpected response shape: {str(data)[:500]}") from exc

        usage = data.get("usage") or {}
        return TargetResponse(
            text=text,
            tokens_in=int(usage.get("prompt_tokens", 0)),
            tokens_out=int(usage.get("completion_tokens", 0)),
            latency_ms=latency_ms,
        )


class OllamaAdapter(OpenAICompatibleAdapter):
    """Ollama via its OpenAI-compatible route."""

    kind = "ollama"

    def __init__(self, endpoint: str, *, model: str, allow_private: bool = False) -> None:
        super().__init__(endpoint, model=model, api_key="", allow_private=allow_private)


class HttpEchoAdapter(TargetAdapter):
    """Generic HTTP POST adapter: sends {messages}, reads a configurable JSON
    path for the reply. For custom chat backends without an OpenAI shape."""

    kind = "http"

    def __init__(
        self, endpoint: str, *, response_path: str = "response",
        allow_private: bool = False, timeout: int | None = None,
    ) -> None:
        super().__init__(endpoint, allow_private=allow_private)
        self.response_path = response_path
        self.timeout = timeout or settings.request_timeout_seconds

    async def complete(self, messages: list[dict[str, str]]) -> TargetResponse:
        self._validate(self.endpoint)
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                resp = await client.post(self.endpoint, json={"messages": messages})
        except httpx.HTTPError as exc:
            raise AdapterError(f"request failed: {exc}") from exc
        latency_ms = int((time.monotonic() - start) * 1000)
        if resp.status_code >= 400:
            raise AdapterError(f"HTTP {resp.status_code}: {resp.text[:500]}")

        node: object = resp.json()
        for key in self.response_path.split("."):
            try:
                node = node[key]  # type: ignore[index]
            except (KeyError, TypeError, IndexError) as exc:
                raise AdapterError(f"response_path {self.response_path!r} not found") from exc
        return TargetResponse(text=str(node), latency_ms=latency_ms)


def build_adapter(
    kind: str, endpoint: str, *, allow_private: bool = False, model: str = "", **kwargs: object,
) -> TargetAdapter:
    """Factory used by the engine and CLI."""
    if kind == "openai":
        return OpenAICompatibleAdapter(
            endpoint, model=model or "default", allow_private=allow_private,
            api_key=str(kwargs.get("api_key", "")),
        )
    if kind == "ollama":
        return OllamaAdapter(endpoint, model=model, allow_private=allow_private)
    if kind == "http":
        return HttpEchoAdapter(
            endpoint, allow_private=allow_private,
            response_path=str(kwargs.get("response_path", "response")),
        )
    raise AdapterError(f"unknown adapter kind {kind!r}")
