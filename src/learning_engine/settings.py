"""The single source of configuration (architecture rule R4).

Phases 3-6 each consumed part of the old `config.py`, leaving behind dead
dataclasses (an OpenAI section pinned to `gpt-3.5-turbo`, a second copy of the
Ollama health probe, a fourth copy of the difficulty instructions) while the
values that *are* live drifted back into literals scattered across the code.
This module ends that: every tunable number, model name, host, and path is
declared here once, typed, and overridable from the environment.

Layout
------
    Settings
    ├── llm   → LLMSettings   (env prefix `LLM__`)   provider models, temperatures, timeouts
    ├── quiz  → QuizSettings  (env prefix `QUIZ__`)  question counts, thresholds, upload limit
    └── app   → AppSettings   (env prefix `APP__`)   title, debug, deployed flag, db path

Nested provider settings use `__` as the separator, so the Ollama chat model is
`LLM__OLLAMA__CHAT_MODEL`. A handful of conventional names (`OPENAI_API_KEY`,
`GOOGLE_AI_API_KEY`, `DEBUG`, `DEPLOYED`, `LEARNING_ENGINE_DB`) keep working
unprefixed, and `_LEGACY_OLLAMA_ENV` / `_legacy_default_provider` keep
pre-Phase-7 `.env` files working. See `.env.example` for the full list.

This module must not import Streamlit (architecture rule R1).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import AliasChoices, BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# `.env` is loaded into os.environ (not just handed to pydantic) because the
# legacy-name shims below read it with os.getenv, and because it is what the
# rest of the process — including Streamlit itself — has always seen.
load_dotenv()

ProviderName = Literal["ollama", "google", "openai", "openrouter"]

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Repo checkout first, then the working directory (which wins if both exist).
_ENV_FILES = (_PROJECT_ROOT / ".env", Path(".env"))


def _config(prefix: str) -> SettingsConfigDict:
    """Shared settings config; only the env prefix differs per section."""
    return SettingsConfigDict(
        env_prefix=prefix,
        env_nested_delimiter="__",
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )


# --------------------------------------------------------------------------- #
# LLM
# --------------------------------------------------------------------------- #


class OllamaSettings(BaseModel):
    """Local Ollama server.

    `base_url` never carries the OpenAI `/v1` suffix — `llm.client.make_client`
    appends it, and `llm.providers` strips it for the `/api/tags` probe. Keeping
    the stored form suffix-free is what removed the six `.replace('/v1', '')`
    call sites in Phase 3.
    """

    host: str = "127.0.0.1"
    port: int = 11434
    chat_model: str = "gemma2:2b"
    scoring_model: str = ""  # blank → reuse chat_model (one local model is the norm)

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def scoring(self) -> str:
        return self.scoring_model or self.chat_model


class GoogleSettings(BaseModel):
    """Gemini via its OpenAI-compatible endpoint (no separate SDK)."""

    base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    chat_model: str = "gemini-2.5-flash"
    scoring_model: str = "gemini-2.5-flash"

    @property
    def scoring(self) -> str:
        return self.scoring_model or self.chat_model


class OpenAISettings(BaseModel):
    """OpenAI proper. `base_url = None` means the SDK default."""

    base_url: str | None = None
    chat_model: str = "gpt-4o-mini"
    scoring_model: str = "gpt-4o-mini"

    @property
    def scoring(self) -> str:
        return self.scoring_model or self.chat_model


class OpenRouterSettings(BaseModel):
    """OpenRouter — one key, many models, including free ones.

    The default is a `:free` model so a student with no budget can run the whole
    app on a key that never bills. Free models are capped per day rather than
    metered; the cap is OpenRouter's to change, so it is not recorded here.
    """

    base_url: str = "https://openrouter.ai/api/v1"
    chat_model: str = "google/gemma-4-31b-it:free"
    scoring_model: str = ""  # blank → reuse chat_model

    @property
    def scoring(self) -> str:
        return self.scoring_model or self.chat_model


# Pre-Phase-7 env names → the nested Ollama field they now map to.
_LEGACY_OLLAMA_ENV = {
    "LOCAL_AI_MODEL": "chat_model",
    "LOCAL_AI_HOST": "host",
    "LOCAL_AI_PORT": "port",
}


def _legacy_default_provider() -> ProviderName | None:
    """Read the old mutually-exclusive `USE_*` flags, if any are set."""
    if os.getenv("USE_LOCAL_AI", "").lower() == "true":
        return "ollama"
    if os.getenv("USE_GOOGLE_AI", "").lower() == "true":
        return "google"
    if os.getenv("USE_OPENAI", "").lower() == "true" or os.getenv("OPENAI_API_KEY"):
        return "openai"
    return None


class LLMSettings(BaseSettings):
    """Provider models plus the generation knobs that used to be literals.

    The temperatures and token limits below were module constants in
    `generation/quiz.py` and `generation/materials.py`; the timeouts were
    default arguments in `llm/client.py` and `llm/providers.py`.
    """

    model_config = _config("LLM__")

    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    google: GoogleSettings = Field(default_factory=GoogleSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    openrouter: OpenRouterSettings = Field(default_factory=OpenRouterSettings)

    default_provider: ProviderName = "ollama"

    # API keys keep their conventional, unprefixed names.
    openai_api_key: str = Field("", validation_alias=AliasChoices("OPENAI_API_KEY"))
    google_api_key: str = Field("", validation_alias=AliasChoices("GOOGLE_AI_API_KEY"))
    openrouter_api_key: str = Field("", validation_alias=AliasChoices("OPENROUTER_API_KEY"))

    generation_temperature: float = 0.7
    scoring_temperature: float = 0.3
    summary_temperature: float = 0.5
    materials_temperature: float = 0.3  # lower → more consistent study materials

    generation_max_tokens: int = 2000
    scoring_max_tokens: int = 700

    request_timeout: float = 120.0  # a full generation call
    probe_timeout: float = 5.0  # a health check / model listing

    @model_validator(mode="before")
    @classmethod
    def _fill_from_legacy_env(cls, data: Any) -> Any:
        """Honor pre-Phase-7 env names when no `LLM__*` equivalent is set.

        Keeps existing `.env` files working after the rename. New names win:
        a legacy value is only used for a field the env source did not supply.
        """
        if not isinstance(data, dict):
            return data

        ollama = dict(data.get("ollama") or {})
        for env_name, field_name in _LEGACY_OLLAMA_ENV.items():
            value = os.getenv(env_name)
            if value and field_name not in ollama:
                ollama[field_name] = value
        if ollama:
            data["ollama"] = ollama

        if "default_provider" not in data:
            legacy = _legacy_default_provider()
            if legacy:
                data["default_provider"] = legacy

        return data

    def api_key(self, provider: ProviderName) -> str:
        """The environment-supplied key for `provider` ("" for Ollama)."""
        return {
            "openai": self.openai_api_key,
            "google": self.google_api_key,
            "openrouter": self.openrouter_api_key,
        }.get(provider, "")


# --------------------------------------------------------------------------- #
# Quiz
# --------------------------------------------------------------------------- #


class QuizSettings(BaseSettings):
    """Limits and thresholds for quiz generation and document handling."""

    model_config = _config("QUIZ__")

    min_questions: int = 3
    max_questions: int = 15
    default_questions: int = 5

    # Documents longer than this are condensed before generation. Summarizing is
    # LOSSY — questions can only cover what survives — so the threshold exists to
    # avoid blowing the context window, not to save tokens. It was 3,000 characters
    # (~750 tokens) when every provider was small; today's defaults hold two orders
    # of magnitude more, so it now sits near the smallest context we support
    # (~8k tokens) and most documents skip summarization entirely.
    summary_threshold: int = 24000
    max_upload_mb: int = 50

    # JSON-encoded when set from the environment, e.g. QUIZ__SUPPORTED_FILE_TYPES='["pdf"]'
    supported_file_types: tuple[str, ...] = ("pdf", "docx", "pptx")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #


def _default_db_path() -> Path:
    return Path.home() / ".learning_engine" / "analytics.db"


class AppSettings(BaseSettings):
    """Presentation and deployment settings."""

    model_config = _config("APP__")

    title: str = "📚 AI Interactive Quiz & Study Materials Generator"
    page_icon: str = "📚"
    layout: Literal["centered", "wide"] = "wide"

    debug: bool = Field(False, validation_alias=AliasChoices("APP__DEBUG", "DEBUG"))

    # Set DEPLOYED=true when hosting (e.g. Streamlit Cloud). Sniffing st.secrets
    # was unreliable — the object exists locally too, so the old check was always
    # true on a laptop (BUG-4).
    deployed: bool = Field(False, validation_alias=AliasChoices("APP__DEPLOYED", "DEPLOYED"))

    db_path: Path = Field(
        default_factory=_default_db_path,
        validation_alias=AliasChoices("APP__DB_PATH", "LEARNING_ENGINE_DB"),
    )


# --------------------------------------------------------------------------- #
# Access
# --------------------------------------------------------------------------- #


class Settings(BaseModel):
    """The whole configuration tree; reach it through `get_settings()`."""

    llm: LLMSettings
    quiz: QuizSettings
    app: AppSettings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, built once on first use.

    Cached rather than constructed at import time: nothing is read from the
    environment until something actually asks (rule R1's sibling — no
    import-time side effects beyond loading `.env`).
    """
    return Settings(llm=LLMSettings(), quiz=QuizSettings(), app=AppSettings())


def reload_settings() -> Settings:
    """Rebuild settings from the current environment (used by tests)."""
    get_settings.cache_clear()
    return get_settings()
