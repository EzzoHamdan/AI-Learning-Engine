"""Session state management for dynamic configuration and API keys."""

import streamlit as st
import json
import os
from typing import Dict, List
from pathlib import Path


class SessionManager:
    """Manages session state for dynamic configuration and API keys."""
    
    def __init__(self):
        """Initialize session manager."""
        self.user_config_file = Path("user_config.json")
        self.is_cloud_deployment = self._detect_cloud_deployment()
        self._init_session_state()
        
    def _detect_cloud_deployment(self) -> bool:
        """Detect if running in cloud deployment by checking if Streamlit secrets are accessible."""
        try:
            # If we can access st.secrets, we're running in Streamlit 
            if hasattr(st, 'secrets'):
                # Try to access secrets 
                _ = st.secrets
                return True
            return False
        except Exception:
            # If accessing secrets fails, we're probably running locally
            return False  
         
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
            
        # Clean up any existing config files in cloud deployments
        if self.is_cloud_deployment:
            self.cleanup_cloud_config()
            
    def cleanup_cloud_config(self):
        """Remove any existing config files in cloud deployments for security."""
        if self.user_config_file.exists():
            try:
                # Read and check if it contains API keys before deleting
                config_data = {}
                try:
                    with open(self.user_config_file, 'r') as f:
                        config_data = json.load(f)
                except:
                    pass
                
                # Delete the file
                os.remove(self.user_config_file)
                
                # Show appropriate message
                if config_data.get("api_keys"):
                    st.sidebar.error("🔒 Removed insecure config file containing API keys!")
                    st.sidebar.info("✅ Your cloud deployment is now secure")
                else:
                    st.sidebar.info("🔒 Removed local config file for security")
                    
                return True
            except Exception as e:
                st.sidebar.warning(f"Could not remove config file: {e}")
                return False
        return True
    
    def show_cloud_key_removal_guide(self):
        """Show guide for removing API keys from cloud deployment."""
        if not self.is_cloud_deployment:
            return
            
        st.sidebar.markdown("---")
        st.sidebar.subheader("🗑️ Remove Old API Keys")
        
        if st.sidebar.button("🚨 Show Key Removal Guide"):
            st.sidebar.markdown("""
            **To completely remove an API key:**
            
            1. Go to **App Settings → Secrets**
            2. **Delete the entire line** for the key:
            ```toml
            # Remove this entire line:
            # GOOGLE_AI_API_KEY = "old_revoked_key"
            ```
            3. **Save** (leave empty if no replacement)
            4. **Restart** your app
            
            ⚠️ **Important:** Deleting the line removes the key completely.
            """)
            
            # Show current status
            status = self.get_cloud_secrets_status()
            if status.get('secrets_accessible'):
                st.sidebar.write("**Current Status:**")
                if status.get('google_configured'):
                    st.sidebar.warning("🔑 Google AI key is currently set")
                else:
                    st.sidebar.success("✅ Google AI key is not set")
                    
                if status.get('openai_configured'):
                    st.sidebar.info("🔑 OpenAI key is currently set")
                else:
                    st.sidebar.info("❌ OpenAI key is not set")
            
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
        """Load saved API keys from user config file or Streamlit secrets."""
        api_keys = {
            "openai": "",
            "google_ai": "",
        }
        
        # In cloud deployments, prioritize Streamlit secrets
        if self.is_cloud_deployment:
            try:
                # Try to load from Streamlit secrets
                if hasattr(st, 'secrets'):
                    api_keys["openai"] = st.secrets.get("OPENAI_API_KEY", "")
                    api_keys["google_ai"] = st.secrets.get("GOOGLE_AI_API_KEY", "")
            except Exception:
                pass  # Secrets not available or not configured
        
        # Fallback to environment variables
        api_keys["openai"] = api_keys["openai"] or os.getenv("OPENAI_API_KEY", "")
        api_keys["google_ai"] = api_keys["google_ai"] or os.getenv("GOOGLE_AI_API_KEY", "")
        
        # Load from user config only if not in cloud deployment
        if not self.is_cloud_deployment and self.user_config_file.exists():
            try:
                with open(self.user_config_file, 'r') as f:
                    user_config = json.load(f)
                    if user_config.get("save_api_keys", False):
                        saved_keys = user_config.get("api_keys", {})
                        # Only update if we don't already have keys from other sources
                        for key, value in saved_keys.items():
                            if not api_keys.get(key):
                                api_keys[key] = value
            except Exception as e:
                if not self.is_cloud_deployment:  # Only show warning for local deployments
                    st.warning(f"Could not load saved configuration: {e}")
                
        return api_keys
        
    def save_user_config(self):
        """Save user configuration to file if requested and not in cloud deployment."""
            
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
            
        if not self.is_cloud_deployment:
            # In local development: show save option with clear warning
            save_keys = st.sidebar.checkbox(
                "💾 Save API keys locally",
                value=st.session_state.save_api_keys,
                help="⚠️ ONLY for local development! Never use in cloud deployments for security reasons."
            )
            st.session_state.save_api_keys = save_keys
            
            # Show warning about cloud deployments
            if save_keys:
                st.sidebar.warning("⚠️ Only use this for local development!")
                st.sidebar.info("🔐 For cloud deployments, use Streamlit secrets instead")
        
        # Save button and secrets guide - different for cloud vs local
        if not self.is_cloud_deployment:
            # LOCAL DEVELOPMENT: Show save button and local setup
            if st.sidebar.button("💾 Save Configuration"):
                if self.save_user_config():
                    st.sidebar.success("✅ Configuration saved locally!")
                else:
                    st.sidebar.error("❌ Failed to save configuration")
                    
                
            # Show current secrets status (without revealing values)
            if hasattr(st, 'secrets'):
                try:
                    has_openai = bool(st.secrets.get("OPENAI_API_KEY", ""))
                    has_google = bool(st.secrets.get("GOOGLE_AI_API_KEY", ""))
                    
                    st.sidebar.write("**Current Secrets Status:**")
                    st.sidebar.write(f"🔑 OpenAI: {'✅ Set' if has_openai else '❌ Not set'}")
                    st.sidebar.write(f"� Google AI: {'✅ Set' if has_google else '❌ Not set'}")
                except:
                    st.sidebar.write("**Secrets:** Not accessible or not configured")
                    
            # Add key removal guide
            self.show_cloud_key_removal_guide()
                
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
