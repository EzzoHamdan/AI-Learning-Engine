"""Tests for settings.py — the single configuration source (rule R4).

Two things are worth pinning down here. First, that the documented env names in
`.env.example` actually reach the fields they claim to. Second, that the legacy
names from before Phase 7 still work, since existing `.env` files on disk use
them and a silent fallback to defaults would be worse than an error.

Every settings object is built with `_env_file=None` so the repository's own
`.env` cannot leak into a test; the environment is then controlled explicitly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from learning_engine.settings import (
    AppSettings,
    LLMSettings,
    QuizSettings,
    get_settings,
    reload_settings,
)

# Anything that could reach a settings field, cleared before every test.
_ENV_VARS = (
    "OPENAI_API_KEY",
    "GOOGLE_AI_API_KEY",
    "LOCAL_AI_MODEL",
    "LOCAL_AI_HOST",
    "LOCAL_AI_PORT",
    "USE_LOCAL_AI",
    "USE_GOOGLE_AI",
    "USE_OPENAI",
    "DEBUG",
    "DEPLOYED",
    "LEARNING_ENGINE_DB",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch):
    """Remove every settings-relevant variable, including the LLM__/QUIZ__/APP__ tree."""
    import os

    for name in list(os.environ):
        if name.startswith(("LLM__", "QUIZ__", "APP__")):
            monkeypatch.delenv(name, raising=False)
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --------------------------------------------------------------------------- #
# Defaults
# --------------------------------------------------------------------------- #


def test_defaults_are_current_models():
    llm = LLMSettings(_env_file=None)
    assert llm.default_provider == "ollama"
    assert llm.google.chat_model == "gemini-2.5-flash"
    # gpt-3.5-turbo was the pre-Phase-7 default and is long since legacy.
    assert llm.openai.chat_model == "gpt-4o-mini"


def test_ollama_base_url_never_carries_the_v1_suffix():
    """Phase 3 removed six `.replace('/v1', '')` sites by storing the URL bare."""
    llm = LLMSettings(_env_file=None)
    assert llm.ollama.base_url == "http://127.0.0.1:11434"
    assert not llm.ollama.base_url.endswith("/v1")


def test_scoring_model_falls_back_to_chat_model_when_blank():
    llm = LLMSettings(_env_file=None)
    assert llm.ollama.scoring_model == ""
    assert llm.ollama.scoring == llm.ollama.chat_model


# --------------------------------------------------------------------------- #
# Environment overrides
# --------------------------------------------------------------------------- #


def test_nested_env_override(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM__OLLAMA__CHAT_MODEL", "llama3.2")
    monkeypatch.setenv("LLM__OLLAMA__PORT", "9999")
    llm = LLMSettings(_env_file=None)
    assert llm.ollama.chat_model == "llama3.2"
    assert llm.ollama.base_url == "http://127.0.0.1:9999"


def test_api_keys_use_their_conventional_unprefixed_names(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "AIza-test")
    llm = LLMSettings(_env_file=None)
    assert llm.api_key("openai") == "sk-test"
    assert llm.api_key("google") == "AIza-test"
    assert llm.api_key("ollama") == ""


def test_quiz_overrides_and_derived_byte_limit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QUIZ__MAX_UPLOAD_MB", "5")
    monkeypatch.setenv("QUIZ__MAX_QUESTIONS", "20")
    quiz = QuizSettings(_env_file=None)
    assert quiz.max_upload_mb == 5
    assert quiz.max_upload_bytes == 5 * 1024 * 1024
    assert quiz.max_questions == 20


def test_app_accepts_both_prefixed_and_short_names(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEPLOYED", "true")
    monkeypatch.setenv("APP__DEBUG", "true")
    monkeypatch.setenv("LEARNING_ENGINE_DB", "/tmp/test-analytics.db")
    app = AppSettings(_env_file=None)
    assert app.deployed is True
    assert app.debug is True
    assert app.db_path == Path("/tmp/test-analytics.db")


def test_db_path_defaults_under_the_home_directory():
    app = AppSettings(_env_file=None)
    assert app.db_path == Path.home() / ".learning_engine" / "analytics.db"


# --------------------------------------------------------------------------- #
# Backwards compatibility with pre-Phase-7 .env files
# --------------------------------------------------------------------------- #


def test_legacy_local_ai_names_still_configure_ollama(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LOCAL_AI_MODEL", "gemma4:31b-cloud")
    monkeypatch.setenv("LOCAL_AI_HOST", "192.168.1.5")
    monkeypatch.setenv("LOCAL_AI_PORT", "1234")
    llm = LLMSettings(_env_file=None)
    assert llm.ollama.chat_model == "gemma4:31b-cloud"
    assert llm.ollama.base_url == "http://192.168.1.5:1234"


def test_new_names_win_over_legacy_names(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LOCAL_AI_MODEL", "old-model")
    monkeypatch.setenv("LLM__OLLAMA__CHAT_MODEL", "new-model")
    assert LLMSettings(_env_file=None).ollama.chat_model == "new-model"


def test_legacy_and_new_names_merge_field_by_field(monkeypatch: pytest.MonkeyPatch):
    """A legacy value fills only the fields the new-style env did not supply."""
    monkeypatch.setenv("LOCAL_AI_MODEL", "legacy-model")
    monkeypatch.setenv("LLM__OLLAMA__PORT", "9999")
    llm = LLMSettings(_env_file=None)
    assert llm.ollama.chat_model == "legacy-model"
    assert llm.ollama.port == 9999


@pytest.mark.parametrize(
    ("flag", "expected"),
    [("USE_LOCAL_AI", "ollama"), ("USE_GOOGLE_AI", "google"), ("USE_OPENAI", "openai")],
)
def test_legacy_use_flags_select_the_default_provider(
    monkeypatch: pytest.MonkeyPatch, flag: str, expected: str
):
    monkeypatch.setenv(flag, "true")
    assert LLMSettings(_env_file=None).default_provider == expected


def test_explicit_default_provider_wins_over_legacy_flags(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USE_OPENAI", "true")
    monkeypatch.setenv("LLM__DEFAULT_PROVIDER", "google")
    assert LLMSettings(_env_file=None).default_provider == "google"


def test_unknown_provider_is_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM__DEFAULT_PROVIDER", "anthropic")
    with pytest.raises(ValueError):
        LLMSettings(_env_file=None)


# --------------------------------------------------------------------------- #
# Access
# --------------------------------------------------------------------------- #


def test_get_settings_is_cached_and_reload_picks_up_changes(monkeypatch: pytest.MonkeyPatch):
    first = get_settings()
    assert get_settings() is first

    monkeypatch.setenv("QUIZ__DEFAULT_QUESTIONS", "11")
    assert get_settings().quiz.default_questions == first.quiz.default_questions

    assert reload_settings().quiz.default_questions == 11
