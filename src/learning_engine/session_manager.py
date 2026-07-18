"""Session state management for dynamic configuration and API keys.

API keys are sourced from environment variables, Streamlit secrets (when
deployed), or entered in the sidebar for the current session. There is no
on-disk key store: the old "save API keys locally" feature wrote plaintext
JSON, and because cloud detection was always true it never actually ran
(BUG-4), so nothing is lost by removing it.
"""

import streamlit as st
import os
from typing import Dict, List


class SessionManager:
    """Manages session state for dynamic configuration and API keys."""

    def __init__(self):
        """Initialize session manager."""
        self.is_cloud_deployment = self._detect_cloud_deployment()
        self._init_session_state()

    def _detect_cloud_deployment(self) -> bool:
        """Detect cloud deployment via an explicit env var.

        Set DEPLOYED=true in the hosting environment (e.g. as a Streamlit Cloud
        secret). Attribute-sniffing st.secrets is unreliable: the object exists
        in every modern Streamlit install, local or cloud, so the old check was
        always true on a laptop (BUG-4).
        """
        return os.getenv("DEPLOYED", "").lower() == "true"

    def _init_session_state(self):
        """Initialize session state variables."""
        # AI Provider selection
        if "ai_provider" not in st.session_state:
            st.session_state.ai_provider = self._get_default_provider()

        # Local AI model selection
        if "selected_local_model" not in st.session_state:
            # Initialize with default model from config
            from learning_engine.settings import LocalAIConfig
            st.session_state.selected_local_model = LocalAIConfig().MODEL_NAME

        # API Keys
        if "api_keys" not in st.session_state:
            st.session_state.api_keys = self._load_saved_api_keys()

        # Provider availability
        if "provider_status" not in st.session_state:
            st.session_state.provider_status = {}

    def _get_default_provider(self) -> str:
        """Determine default AI provider based on availability."""
        # Check environment variables first
        if os.getenv("USE_LOCAL_AI", "false").lower() == "true":
            return "Local AI (Ollama)"
        elif os.getenv("USE_GOOGLE_AI", "false").lower() == "true":
            return "Google AI"
        elif os.getenv("OPENAI_API_KEY"):
            return "OpenAI"
        else:
            return "Local AI (Ollama)"  # Default fallback

    def _load_saved_api_keys(self) -> Dict[str, str]:
        """Load API keys from Streamlit secrets (when deployed) and environment."""
        api_keys = {
            "openai": "",
            "google_ai": "",
        }

        # In cloud deployments, prioritize Streamlit secrets
        if self.is_cloud_deployment:
            try:
                if hasattr(st, 'secrets'):
                    api_keys["openai"] = st.secrets.get("OPENAI_API_KEY", "")
                    api_keys["google_ai"] = st.secrets.get("GOOGLE_AI_API_KEY", "")
            except Exception:
                pass  # Secrets not available or not configured

        # Fallback to environment variables
        api_keys["openai"] = api_keys["openai"] or os.getenv("OPENAI_API_KEY", "")
        api_keys["google_ai"] = api_keys["google_ai"] or os.getenv("GOOGLE_AI_API_KEY", "")

        return api_keys

    def get_api_key(self, provider: str) -> str:
        """Get API key for specified provider."""
        key_mapping = {
            "OpenAI": "openai",
            "Google AI": "google_ai"
        }
        key_name = key_mapping.get(provider, "")
        return st.session_state.api_keys.get(key_name, "")

    def set_api_key(self, provider: str, key: str):
        """Set API key for specified provider."""
        key_mapping = {
            "OpenAI": "openai",
            "Google AI": "google_ai"
        }
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
        """Check if Ollama server is running."""
        try:
            from learning_engine.local_ai_client import is_ollama_running, list_available_models

            if is_ollama_running("http://127.0.0.1:11434"):
                models = list_available_models("http://127.0.0.1:11434")
                if models:
                    return True, f"Running with {len(models)} models"
                else:
                    return False, "Running but no models available"
            else:
                return False, "Server not running"
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def update_provider_status(self):
        """Update status of all providers."""
        providers = ["Local AI (Ollama)", "Google AI", "OpenAI"]
        for provider in providers:
            available, message = self.check_provider_availability(provider)
            st.session_state.provider_status[provider] = {
                "available": available,
                "message": message
            }

    def get_available_providers(self) -> List[str]:
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
            help="Enter your OpenAI API key for GPT models"
        )
        if openai_key != current_openai:
            self.set_api_key("OpenAI", openai_key)

        # Google AI API Key
        current_google = self.get_api_key("Google AI")
        google_key = st.sidebar.text_input(
            "Google AI API Key:",
            value=current_google,
            type="password",
            help="Enter your Google AI API key for Gemini models"
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
        for provider in ["Local AI (Ollama)", "Google AI", "OpenAI"]:
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
            help="Select your preferred AI provider"
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
