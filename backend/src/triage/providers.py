"""LLM provider abstraction (BE-06).

A narrow ``LLMProvider`` Protocol plus one adapter per SDK. This is the swap seam
for model portability (Claude -> Gemini -> ...) with zero framework dependency,
mirroring the storage layer's isolated interface. The classifier depends only on
the Protocol, so it stays provider-agnostic and unit-testable with a fake.

Alternatives considered (Pydantic AI, Instructor, LiteLLM, LangChain) are
documented in docs/architecture.md.
"""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import structlog

if TYPE_CHECKING:
    from .config import Settings

log = structlog.get_logger()


def _is_transient_error(e: Exception) -> bool:
    # Check standard attributes for HTTP status codes
    for attr in ("status_code", "code"):
        if hasattr(e, attr):
            val = getattr(e, attr)
            if isinstance(val, int) and val in (429, 500, 502, 503, 504, 529):
                return True
    
    # Check class name
    name = type(e).__name__
    if name in (
        "RateLimitError",
        "InternalServerError",
        "ServerError",
        "APIStatusError",
        "ServiceUnavailable",
        "BadGateway",
        "GatewayTimeout",
        "HTTPStatusError",
        "APIError",
    ):
        return True
        
    # Fallback to string checks for common messages
    msg = str(e).lower()
    if "503" in msg or "429" in msg or "rate limit" in msg or "unavailable" in msg or "temporarily" in msg:
        return True
        
    return False


def retry_on_transient_error(max_attempts: int = 5, initial_delay: float = 1.0, backoff_factor: float = 2.0):
    def decorator(func):
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if not _is_transient_error(e) or attempt == max_attempts:
                        raise
                    
                    log.warning(
                        "llm.provider.transient_error",
                        attempt=attempt,
                        next_delay=delay,
                        error_type=type(e).__name__,
                        error_msg=str(e),
                    )
                    
                    sleep_time = delay + random.uniform(0, 1.0)
                    time.sleep(sleep_time)
                    delay *= backoff_factor
            return func(*args, **kwargs)
        return wrapper
    return decorator


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal contract: turn (system, messages) into raw completion text."""

    name: str
    model: str

    def complete(
        self,
        system: str,
        messages: list[dict],
        *,
        temperature: float,
        max_tokens: int,
    ) -> str: ...


class AnthropicProvider:
    """Adapter over the Anthropic Messages API."""

    name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        import anthropic  # lazy: keep SDK import out of test paths that use a fake

        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    @retry_on_transient_error()
    def complete(
        self, system: str, messages: list[dict], *, temperature: float, max_tokens: int
    ) -> str:
        resp = self._client.messages.create(
            model=self.model,
            system=system,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return "".join(block.text for block in resp.content if block.type == "text")


class GeminiProvider:
    """Adapter over the Google Gemini API (google-genai).

    Roadmap-ready: only this adapter changes when switching the classifier to
    Gemini; the classifier and prompts stay untouched.
    """

    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        from google import genai  # lazy import

        self._client = genai.Client(api_key=api_key)
        self.model = model

    @retry_on_transient_error()
    def complete(
        self, system: str, messages: list[dict], *, temperature: float, max_tokens: int
    ) -> str:
        from google.genai import types

        # Flatten the chat turns into Gemini's contents format.
        contents = [
            types.Content(
                role="user" if m["role"] == "user" else "model",
                parts=[types.Part.from_text(text=m["content"])],
            )
            for m in messages
        ]
        resp = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
            ),
        )
        return resp.text or ""


class OpenAIProvider:
    """Adapter over the OpenAI Chat Completions API.

    Used mainly by the cross-family judge, but shares the same ``LLMProvider``
    contract as the classifier adapters.
    """

    name = "openai"

    def __init__(self, api_key: str, model: str) -> None:
        from openai import OpenAI  # lazy import

        self._client = OpenAI(api_key=api_key)
        self.model = model

    @retry_on_transient_error()
    def complete(
        self, system: str, messages: list[dict], *, temperature: float, max_tokens: int
    ) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, *messages],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or ""


# One place that knows how to build any adapter, reused by classifier and judge.
_ADAPTERS = {
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
}


def build_provider(name: str, api_key: str, model: str) -> LLMProvider:
    """Construct an adapter by provider name."""
    adapter = _ADAPTERS.get(name.lower())
    if adapter is None:
        raise ValueError(f"Unsupported provider: {name!r}. Valid: {sorted(_ADAPTERS)}.")
    return adapter(api_key=api_key, model=model)


def get_provider(settings: Settings) -> LLMProvider:
    """Build the classifier adapter from ``settings.classifier_provider``."""
    provider = settings.classifier_provider.lower()
    key_field = {"anthropic": settings.anthropic_api_key, "gemini": settings.google_api_key}.get(
        provider
    )
    if key_field is None:
        raise ValueError(f"Unsupported classifier_provider: {settings.classifier_provider!r}")
    return build_provider(provider, key_field.get_secret_value(), settings.classifier_model)
