"""The single LLM client. Every provider speaks OpenAI, so this is tiny.

Replaces google_ai_client.py, local_ai_client.py, and the mock hierarchy in
ai_client_factory.py. Errors are raised as typed exceptions rather than being
smuggled back as fake "successful" responses (the old MockClient anti-pattern);
the UI layer decides how to present them.

This module must not import Streamlit (architecture rule R1).
"""

from __future__ import annotations

from openai import OpenAI

from learning_engine.llm.providers import Provider, ProviderConfig


class ProviderUnavailable(Exception):
    """The selected provider cannot be used (no API key, server down, ...)."""


class GenerationFailed(Exception):
    """A generation call failed or returned unusable content."""


def make_client(cfg: ProviderConfig, timeout: float = 120) -> OpenAI:
    """Build an OpenAI SDK client pointed at the given provider.

    Ollama's base URL is stored without `/v1`, so it is appended here; any
    non-empty api_key works for Ollama. Google uses its OpenAI-compatible
    endpoint; OpenAI uses the SDK default (base_url=None).
    """
    if cfg.provider is Provider.OLLAMA:
        base_url = f"{(cfg.base_url or 'http://127.0.0.1:11434').rstrip('/')}/v1"
        api_key = cfg.api_key or "ollama"
    else:
        base_url = cfg.base_url
        api_key = cfg.api_key

    return OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
