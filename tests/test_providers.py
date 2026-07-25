"""Tests for llm/providers.py and llm/client.py — the provider data table.

Provider differences are data, not code: a base URL, a key, two model names. So
what is worth pinning down is that the table stays *complete*. Every Provider
must have a display label (the sidebar renders `DISPLAY_NAMES.values()` and
stores the label in session state, so a missing entry is a KeyError at startup),
and that label must map back to the same Provider.

The OpenRouter cases exist because it is the free-tier route: if its base URL or
`:free` default model drifts, students following the README start paying.
"""

from __future__ import annotations

import pytest

from learning_engine.llm.client import make_client
from learning_engine.llm.providers import (
    DISPLAY_NAMES,
    Provider,
    ProviderConfig,
    health_check,
    provider_from_display,
)
from learning_engine.settings import LLMSettings, ProviderName, get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --------------------------------------------------------------------------- #
# The table is complete
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("provider", list(Provider))
def test_every_provider_has_a_label_that_maps_back(provider: Provider):
    """A provider with no label crashes the sidebar; one with a stale label
    silently resolves to the wrong client."""
    label = DISPLAY_NAMES[provider]
    assert provider_from_display(label) is provider


def test_provider_enum_and_the_settings_literal_agree():
    """`LLM__DEFAULT_PROVIDER` is validated against ProviderName, then passed to
    `Provider(...)` — a name in one and not the other fails only at runtime."""
    assert {p.value for p in Provider} == set(ProviderName.__args__)


@pytest.mark.parametrize("provider", list(Provider))
def test_every_provider_has_settings_and_a_key_lookup(provider: Provider):
    llm = LLMSettings(_env_file=None)
    assert hasattr(llm, provider.value), f"LLMSettings has no `{provider.value}` section"
    assert llm.api_key(provider.value) == ""  # no key in the environment


def test_provider_from_display_rejects_an_unknown_label():
    with pytest.raises(ValueError):
        provider_from_display("Nonexistent AI")


# --------------------------------------------------------------------------- #
# OpenRouter — the free route
# --------------------------------------------------------------------------- #


def test_openrouter_defaults_to_a_free_model():
    """The `:free` suffix is what makes the key non-billable. Losing it is the
    one drift that costs a student money without any error."""
    openrouter = LLMSettings(_env_file=None).openrouter
    assert openrouter.chat_model.endswith(":free")
    assert openrouter.base_url == "https://openrouter.ai/api/v1"


def test_openrouter_scoring_falls_back_to_the_chat_model():
    openrouter = LLMSettings(_env_file=None).openrouter
    assert openrouter.scoring_model == ""
    assert openrouter.scoring == openrouter.chat_model


def test_openrouter_client_keeps_the_v1_suffix_it_was_given():
    """Only Ollama gets `/v1` appended; OpenRouter's URL already carries it and
    must not be doubled."""
    cfg = ProviderConfig(
        provider=Provider.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-test",
        chat_model="google/gemma-4-31b-it:free",
        scoring_model="google/gemma-4-31b-it:free",
    )
    client = make_client(cfg)
    assert str(client.base_url).rstrip("/") == "https://openrouter.ai/api/v1"
    assert client.api_key == "sk-or-test"


def test_openrouter_health_check_only_needs_a_key():
    """Cloud providers are not probed over the network — a key present is the
    whole check, so an offline student still sees an accurate status."""
    cfg = ProviderConfig(
        provider=Provider.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        api_key="",
        chat_model="m",
        scoring_model="m",
    )
    assert health_check(cfg) == (False, "API key not provided")

    ok, message = health_check(ProviderConfig(**{**cfg.__dict__, "api_key": "sk-or-test"}))
    assert ok and message == "API key available"
