"""Provider definitions and a single health-check for every LLM provider.

Every provider we support now speaks the OpenAI chat-completions protocol, so
the only per-provider differences are the base URL, the API key, and the model
names. This module holds that data (ProviderConfig) plus the one Ollama
`/api/tags` probe that used to be copied in six places.

This module must not import Streamlit (architecture rule R1).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import requests

from learning_engine.settings import get_settings


class Provider(str, Enum):
    OLLAMA = "ollama"
    GOOGLE = "google"
    OPENAI = "openai"


# Human-facing labels stored in session state / shown in the sidebar.
DISPLAY_NAMES: dict[Provider, str] = {
    Provider.OLLAMA: "Local AI (Ollama)",
    Provider.GOOGLE: "Google AI",
    Provider.OPENAI: "OpenAI",
}


def provider_from_display(name: str) -> Provider:
    """Map a UI display label back to a Provider."""
    for provider, label in DISPLAY_NAMES.items():
        if label == name:
            return provider
    raise ValueError(f"Unknown provider: {name!r}")


@dataclass(frozen=True)
class ProviderConfig:
    """Everything needed to talk to one provider.

    base_url is stored WITHOUT the OpenAI `/v1` suffix for Ollama (make_client
    appends it); for Google it is the full OpenAI-compatible endpoint; for
    OpenAI it is None (the SDK default).
    """

    provider: Provider
    base_url: str | None
    api_key: str
    chat_model: str
    scoring_model: str

    @property
    def display_name(self) -> str:
        return DISPLAY_NAMES[self.provider]


def _tags_url(base_url: str) -> str:
    """Normalize an Ollama base URL (with or without /v1) to its /api/tags URL."""
    clean = base_url.rstrip("/")
    if clean.endswith("/v1"):
        clean = clean[: -len("/v1")]
    return f"{clean}/api/tags"


def list_ollama_models(base_url: str, timeout: float | None = None) -> list[str]:
    """Return the model names available on an Ollama server (empty on failure).

    `timeout` defaults to `LLM__PROBE_TIMEOUT`.
    """
    settings = get_settings().llm
    try:
        resp = requests.get(
            _tags_url(base_url), timeout=settings.probe_timeout if timeout is None else timeout
        )
        if resp.status_code == 200:
            return [m["name"] for m in resp.json().get("models", [])]
    except requests.RequestException:
        pass
    return []


def health_check(cfg: ProviderConfig, timeout: float | None = None) -> tuple[bool, str]:
    """One health check for all providers.

    Ollama is probed over HTTP (`GET /api/tags`); cloud providers just need a
    key present. Returns (ok, human-readable message).
    """
    settings = get_settings().llm
    if cfg.provider is Provider.OLLAMA:
        base = cfg.base_url or settings.ollama.base_url
        try:
            resp = requests.get(
                _tags_url(base), timeout=settings.probe_timeout if timeout is None else timeout
            )
        except requests.RequestException:
            return False, "Server not running"
        if resp.status_code != 200:
            return False, f"Server error ({resp.status_code})"
        models = [m["name"] for m in resp.json().get("models", [])]
        if not models:
            return False, "Running but no models installed"
        return True, f"Running with {len(models)} models"

    if not cfg.api_key:
        return False, "API key not provided"
    return True, "API key available"
