"""Centralized settings (BE-02).

Loaded from the environment / ``.env`` via pydantic-settings. ``get_settings`` is
cached so the whole app shares one immutable ``Settings`` instance.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root (…/message-triage-agent), used as the default storage location.
_REPO_ROOT = Path(__file__).resolve().parents[3]

# API key field required for each provider (see providers.py).
_PROVIDER_KEY_FIELD = {
    "anthropic": "anthropic_api_key",
    "gemini": "google_api_key",
    "openai": "openai_api_key",
}
# Providers valid for the classifier (the judge additionally allows "openai").
_CLASSIFIER_PROVIDERS = ("anthropic", "gemini")
# Model family per provider, used for the judge's cross-family bias check.
_PROVIDER_FAMILY = {"anthropic": "anthropic", "gemini": "google", "openai": "openai"}


class Settings(BaseSettings):
    """Application configuration.

    Only the API key for the *selected* ``classifier_provider`` is mandatory; the
    others are optional so a Claude-only or Gemini-only deployment still boots.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Model access
    classifier_provider: str = "anthropic"
    anthropic_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None  # judge (cross-family)

    classifier_model: str = "claude-sonnet-5"
    # Judge: leave judge_provider unset to auto-pick a cross-family provider whose
    # key is present (openai → gemini), falling back to the classifier's family.
    # Set it explicitly (with a matching judge_model) to pin the judge.
    judge_provider: str | None = None
    judge_model: str = "gpt-4o"

    # Generation
    temperature: float = 0.0
    max_tokens: int = 4096
    max_retries: int = 2

    # Infra
    log_level: str = "INFO"
    storage_path: Path = _REPO_ROOT / "storage"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost"]

    @model_validator(mode="after")
    def _require_selected_provider_key(self) -> Settings:
        provider = self.classifier_provider.lower()
        if provider not in _CLASSIFIER_PROVIDERS:
            raise ValueError(
                f"Unknown classifier_provider={provider!r}. "
                f"Valid options: {list(_CLASSIFIER_PROVIDERS)}."
            )
        key_field = _PROVIDER_KEY_FIELD[provider]
        if getattr(self, key_field) is None:
            raise ValueError(
                f"classifier_provider={provider!r} requires {key_field.upper()} to be set."
            )

        # If the judge provider is pinned, validate it and require its key.
        if self.judge_provider is not None:
            jp = self.judge_provider.lower()
            if jp not in _PROVIDER_KEY_FIELD:
                raise ValueError(
                    f"Unknown judge_provider={jp!r}. Valid options: {sorted(_PROVIDER_KEY_FIELD)}."
                )
            if getattr(self, _PROVIDER_KEY_FIELD[jp]) is None:
                raise ValueError(
                    f"judge_provider={jp!r} requires {_PROVIDER_KEY_FIELD[jp].upper()} to be set."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached settings instance."""
    return Settings()
