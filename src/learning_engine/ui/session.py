"""Session state management for dynamic configuration and API keys.

Moved from learning_engine.session_manager: this class renders sidebar widgets
and owns Streamlit session keys, so it lives in the UI layer (rule R1).

API keys are sourced from environment variables, Streamlit secrets (when
deployed), or entered in the sidebar for the current session. There is no
on-disk key store: the old "save API keys locally" feature wrote plaintext
JSON, and because cloud detection was always true it never actually ran
(BUG-4), so nothing is lost by removing it.
"""

import streamlit as st

from learning_engine.llm.providers import DISPLAY_NAMES, Provider, ProviderConfig, health_check
from learning_engine.settings import get_settings


class SessionManager:
    """Manages session state for dynamic configuration and API keys."""

    def __init__(self):
        """Initialize session manager."""
        self.settings = get_settings()
        self.is_cloud_deployment = self.settings.app.deployed
        self._init_session_state()

    def _init_session_state(self):
        """Initialize session state variables."""
        # AI Provider selection
        if "ai_provider" not in st.session_state:
            st.session_state.ai_provider = self._get_default_provider()

        # Local AI model selection
        if "selected_local_model" not in st.session_state:
            st.session_state.selected_local_model = self.settings.llm.ollama.chat_model

        # API Keys
        if "api_keys" not in st.session_state:
            st.session_state.api_keys = self._load_saved_api_keys()

        # Provider availability
        if "provider_status" not in st.session_state:
            st.session_state.provider_status = {}

    def _get_default_provider(self) -> str:
        """The display name of the configured default provider (LLM__DEFAULT_PROVIDER)."""
        return DISPLAY_NAMES[Provider(self.settings.llm.default_provider)]

    # Display name → the session-state slot and Streamlit-secret name for its key.
    _KEY_SLOTS = {
        "OpenAI": ("openai", "OPENAI_API_KEY"),
        "Google AI": ("google_ai", "GOOGLE_AI_API_KEY"),
        "OpenRouter": ("openrouter", "OPENROUTER_API_KEY"),
    }

    def _load_saved_api_keys(self) -> dict[str, str]:
        """Load API keys from Streamlit secrets (when deployed) and settings."""
        api_keys = {slot: "" for slot, _ in self._KEY_SLOTS.values()}

        # In cloud deployments, prioritize Streamlit secrets
        if self.is_cloud_deployment:
            try:
                for slot, secret_name in self._KEY_SLOTS.values():
                    api_keys[slot] = st.secrets.get(secret_name, "")
            except Exception:
                pass  # Secrets not available or not configured

        # Fall back to the environment (via settings)
        api_keys["openai"] = api_keys["openai"] or self.settings.llm.openai_api_key
        api_keys["google_ai"] = api_keys["google_ai"] or self.settings.llm.google_api_key
        api_keys["openrouter"] = api_keys["openrouter"] or self.settings.llm.openrouter_api_key

        return api_keys

    def get_api_key(self, provider: str) -> str:
        """Get API key for specified provider."""
        slot = self._KEY_SLOTS.get(provider)
        return st.session_state.api_keys.get(slot[0], "") if slot else ""

    def set_api_key(self, provider: str, key: str):
        """Set API key for specified provider."""
        slot = self._KEY_SLOTS.get(provider)
        if slot:
            st.session_state.api_keys[slot[0]] = key

    def check_provider_availability(self, provider: str) -> tuple[bool, str]:
        """Check if a provider is available and return status message."""
        if provider == "Local AI (Ollama)":
            return self._check_ollama_availability()
        elif provider in self._KEY_SLOTS:
            if not self.get_api_key(provider):
                return False, "API key not provided"
            return True, "API key available"
        else:
            return False, "Unknown provider"

    def _check_ollama_availability(self) -> tuple[bool, str]:
        """Check whether the local Ollama server is running and has models."""
        cfg = ProviderConfig(
            provider=Provider.OLLAMA,
            base_url=self.settings.llm.ollama.base_url,
            api_key="ollama",
            chat_model="",
            scoring_model="",
        )
        return health_check(cfg)

    def update_provider_status(self):
        """Update status of all providers."""
        for provider in DISPLAY_NAMES.values():
            available, message = self.check_provider_availability(provider)
            st.session_state.provider_status[provider] = {
                "available": available,
                "message": message,
            }

    def get_available_providers(self) -> list[str]:
        """Get list of available providers."""
        available = []
        for provider, status in st.session_state.provider_status.items():
            if status.get("available", False):
                available.append(provider)
        return available

    def render_api_key_inputs(self):
        """Render API key input fields in sidebar (session-scoped)."""
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔐 API Configuration")
        st.sidebar.caption(
            "Keys are used for this session only. For persistent config, set "
            "OPENAI_API_KEY / GOOGLE_AI_API_KEY / OPENROUTER_API_KEY in your "
            "environment or, when deployed, in Streamlit secrets."
        )
        st.sidebar.info(
            "💸 **No budget?** You never have to pay to use this app. Ollama needs "
            "no key at all, and both [Google AI Studio](https://aistudio.google.com/app/apikey) "
            "and [OpenRouter](https://openrouter.ai/keys) issue keys with a free "
            "tier — no card required. Each caps how many requests a day you get, "
            "and both change those caps, so check their own limits pages for "
            "today's number."
        )

        # Free-tier-capable providers first — a student with no card can start here.
        openrouter_model = self.settings.llm.openrouter.chat_model
        for provider, label, help_text in (
            (
                "Google AI",
                "Google AI API Key:",
                "Free-tier key from aistudio.google.com/app/apikey — Gemini and Gemma models",
            ),
            (
                "OpenRouter",
                "OpenRouter API Key:",
                f"Key from openrouter.ai/keys. Default model is {openrouter_model}, "
                "which costs nothing but is capped per day.",
            ),
            ("OpenAI", "OpenAI API Key:", "Enter your OpenAI API key for GPT models (paid)"),
        ):
            current = self.get_api_key(provider)
            entered = st.sidebar.text_input(label, value=current, type="password", help=help_text)
            if entered != current:
                self.set_api_key(provider, entered)

    def render_provider_selector(self) -> str:
        """Render provider selector with status indicators."""
        st.sidebar.subheader("🤖 AI Provider Selection")

        # Update provider status
        self.update_provider_status()

        # Create options with status indicators
        provider_options = []
        for provider in DISPLAY_NAMES.values():
            status = st.session_state.provider_status.get(provider, {})
            if status.get("available", False):
                indicator = "✅"
            else:
                indicator = "❌"
            provider_options.append(f"{indicator} {provider}")

        # Find current selection index
        current_provider = st.session_state.ai_provider
        current_index = 0
        for i, option in enumerate(provider_options):
            if current_provider in option:
                current_index = i
                break

        # Provider selection
        selected_option = st.sidebar.selectbox(
            "Choose AI Provider:",
            provider_options,
            index=current_index,
            help="Select your preferred AI provider",
        )

        # Extract provider name from selection
        selected_provider = selected_option.split(" ", 1)[1]  # Remove emoji indicator
        st.session_state.ai_provider = selected_provider

        # Show provider status
        status = st.session_state.provider_status.get(selected_provider, {})
        if status.get("available", False):
            st.sidebar.success(f"✅ {status.get('message', 'Ready')}")
        else:
            st.sidebar.warning(f"⚠️ {status.get('message', 'Not available')}")

        return selected_provider
