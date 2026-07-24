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

    def _load_saved_api_keys(self) -> dict[str, str]:
        """Load API keys from Streamlit secrets (when deployed) and settings."""
        api_keys = {"openai": "", "google_ai": ""}

        # In cloud deployments, prioritize Streamlit secrets
        if self.is_cloud_deployment:
            try:
                api_keys["openai"] = st.secrets.get("OPENAI_API_KEY", "")
                api_keys["google_ai"] = st.secrets.get("GOOGLE_AI_API_KEY", "")
            except Exception:
                pass  # Secrets not available or not configured

        # Fall back to the environment (via settings)
        api_keys["openai"] = api_keys["openai"] or self.settings.llm.openai_api_key
        api_keys["google_ai"] = api_keys["google_ai"] or self.settings.llm.google_api_key

        return api_keys

    def get_api_key(self, provider: str) -> str:
        """Get API key for specified provider."""
        key_mapping = {"OpenAI": "openai", "Google AI": "google_ai"}
        key_name = key_mapping.get(provider, "")
        return st.session_state.api_keys.get(key_name, "")

    def set_api_key(self, provider: str, key: str):
        """Set API key for specified provider."""
        key_mapping = {"OpenAI": "openai", "Google AI": "google_ai"}
        key_name = key_mapping.get(provider, "")
        if key_name:
            st.session_state.api_keys[key_name] = key

    def check_provider_availability(self, provider: str) -> tuple[bool, str]:
        """Check if a provider is available and return status message."""
        if provider == "Local AI (Ollama)":
            return self._check_ollama_availability()
        elif provider == "Google AI":
            api_key = self.get_api_key(provider)
            if not api_key:
                return False, "API key not provided"
            return True, "API key available"
        elif provider == "OpenAI":
            api_key = self.get_api_key(provider)
            if not api_key:
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
            "OPENAI_API_KEY / GOOGLE_AI_API_KEY in your environment or, when "
            "deployed, in Streamlit secrets."
        )

        # OpenAI API Key
        current_openai = self.get_api_key("OpenAI")
        openai_key = st.sidebar.text_input(
            "OpenAI API Key:",
            value=current_openai,
            type="password",
            help="Enter your OpenAI API key for GPT models",
        )
        if openai_key != current_openai:
            self.set_api_key("OpenAI", openai_key)

        # Google AI API Key
        current_google = self.get_api_key("Google AI")
        google_key = st.sidebar.text_input(
            "Google AI API Key:",
            value=current_google,
            type="password",
            help="Enter your Google AI API key for Gemini models",
        )
        if google_key != current_google:
            self.set_api_key("Google AI", google_key)

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
