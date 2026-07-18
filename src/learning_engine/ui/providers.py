"""Resolve the selected provider to a validated config + a cached OpenAI client.

Moved from learning_engine.ai_client_factory: resolution reads Streamlit
session state and caches with st.cache_resource, so it belongs to the UI
layer (rule R1). On failure it raises ProviderUnavailable instead of
returning a fake "successful" client, and it never switches providers
silently — the pages decide what to show.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import streamlit as st
from openai import OpenAI

from learning_engine.llm.client import ProviderUnavailable, make_client
from learning_engine.llm.providers import (
    GOOGLE_OPENAI_BASE_URL,
    Provider,
    ProviderConfig,
    health_check,
    list_ollama_models,
    provider_from_display,
)
from learning_engine.settings import GoogleAIConfig, LocalAIConfig, OpenAIConfig
from learning_engine.ui.session import SessionManager


@dataclass(frozen=True)
class ActiveProvider:
    """The resolved provider for this rerun: a client when ok, a reason when not."""

    client: OpenAI | None
    cfg: ProviderConfig | None
    display_name: str
    ok: bool
    error: str | None


def build_provider_config(provider: Provider, session_manager: SessionManager) -> ProviderConfig:
    """Assemble a ProviderConfig from settings defaults + session keys/model."""
    if provider is Provider.OLLAMA:
        local = LocalAIConfig()
        model = st.session_state.get("selected_local_model", local.MODEL_NAME)
        return ProviderConfig(
            provider=provider,
            base_url=f"http://{local.HOST}:{local.PORT}",  # /v1 appended in make_client
            api_key="ollama",
            chat_model=model,
            scoring_model=model,
        )
    if provider is Provider.GOOGLE:
        google = GoogleAIConfig()
        return ProviderConfig(
            provider=provider,
            base_url=GOOGLE_OPENAI_BASE_URL,
            api_key=session_manager.get_api_key("Google AI"),
            chat_model=google.CHAT_MODEL,
            scoring_model=google.SCORING_MODEL,
        )
    openai_cfg = OpenAIConfig()
    return ProviderConfig(
        provider=provider,
        base_url=None,
        api_key=session_manager.get_api_key("OpenAI"),
        chat_model=openai_cfg.MODEL,
        scoring_model=openai_cfg.SCORING_MODEL,
    )


def resolve_provider(session_manager: SessionManager) -> ProviderConfig:
    """Validate the currently-selected provider and return its config.

    Raises ProviderUnavailable(reason) on failure instead of falling back to a
    mock client or switching providers behind the user's back.
    """
    provider = provider_from_display(st.session_state.ai_provider)
    cfg = build_provider_config(provider, session_manager)

    if provider is Provider.OLLAMA:
        models = list_ollama_models(cfg.base_url)
        if not models:
            _, message = health_check(cfg)  # distinguishes "down" vs "no models"
            raise ProviderUnavailable(message)
        if cfg.chat_model not in models:
            # Selected model is gone; fall back to the first available and persist it.
            cfg = replace(cfg, chat_model=models[0], scoring_model=models[0])
            st.session_state.selected_local_model = models[0]
        return cfg

    ok, message = health_check(cfg)
    if not ok:
        raise ProviderUnavailable(message)
    return cfg


@st.cache_resource
def get_client(cfg: ProviderConfig) -> OpenAI:
    """Return a cached OpenAI client for cfg (keyed on the frozen config).

    Caching means the client is built once per (provider, key, url) instead of
    on every Streamlit rerun.
    """
    return make_client(cfg)


def resolve_active_provider(session_manager: SessionManager) -> ActiveProvider:
    """Resolve the selection to an ActiveProvider bundle for this rerun.

    On failure returns a disabled state with the reason instead of a mock
    client, and never switches providers silently.
    """
    try:
        cfg = resolve_provider(session_manager)
        return ActiveProvider(get_client(cfg), cfg, cfg.display_name, True, None)
    except ProviderUnavailable as exc:
        return ActiveProvider(None, None, st.session_state.ai_provider, False, str(exc))
