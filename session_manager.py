"""Session state management for dynamic configuration and API keys."""

import streamlit as st
import json
import os
from typing import Dict, Any, Optional, List
from pathlib import Path


class SessionManager:
    """Manages session state for dynamic configuration and API keys."""
    
    def __init__(self):
        """Initialize session manager."""
        self.user_config_file = Path("user_config.json")
        self._init_session_state()
        
    def _init_session_state(self):
        """Initialize session state variables."""
        # AI Provider selection
        if "ai_provider" not in st.session_state:
            st.session_state.ai_provider = self._get_default_provider()
            
        # Local AI model selection
        if "selected_local_model" not in st.session_state:
            # Initialize with default model from config
            from config import LocalAIConfig
            st.session_state.selected_local_model = LocalAIConfig().MODEL_NAME
            
        # API Keys
        if "api_keys" not in st.session_state:
            st.session_state.api_keys = self._load_saved_api_keys()
            
        # Provider availability
        if "provider_status" not in st.session_state:
            st.session_state.provider_status = {}
            
        # Configuration flags
        if "save_api_keys" not in st.session_state:
            st.session_state.save_api_keys = False
            
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
        """Load saved API keys from user config file."""
        api_keys = {
            "openai": os.getenv("OPENAI_API_KEY", ""),
            "google_ai": os.getenv("GOOGLE_AI_API_KEY", ""),
        }
        
        # Load from user config if exists and user previously chose to save
        if self.user_config_file.exists():
            try:
                with open(self.user_config_file, 'r') as f:
                    user_config = json.load(f)
                    if user_config.get("save_api_keys", False):
                        saved_keys = user_config.get("api_keys", {})
                        api_keys.update(saved_keys)
            except Exception as e:
                st.warning(f"Could not load saved configuration: {e}")
                
        return api_keys
        
    def save_user_config(self):
        """Save user configuration to file if requested."""
        if st.session_state.save_api_keys:
            try:
                config = {
                    "save_api_keys": True,
                    "api_keys": st.session_state.api_keys,
                    "preferred_provider": st.session_state.ai_provider
                }
                with open(self.user_config_file, 'w') as f:
                    json.dump(config, f, indent=2)
                return True
            except Exception as e:
                st.error(f"Failed to save configuration: {e}")
                return False
        return True
        
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
            import requests
            from local_ai_client import is_ollama_running, list_available_models
            
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
        """Render API key input fields in sidebar."""
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔐 API Configuration")
        
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
            help="Enter your Google AI API key for Gemma models"
        )
        if google_key != current_google:
            self.set_api_key("Google AI", google_key)
            
        # Save configuration option
        save_keys = st.sidebar.checkbox(
            "💾 Save API keys locally",
            value=st.session_state.save_api_keys,
            help="Save API keys to local config file for next session"
        )
        st.session_state.save_api_keys = save_keys
        
        # Save button
        if st.sidebar.button("💾 Save Configuration"):
            if self.save_user_config():
                st.sidebar.success("✅ Configuration saved!")
            else:
                st.sidebar.error("❌ Failed to save configuration")
                
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
