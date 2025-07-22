"""
AI Client Factory with graceful error handling and dynamic provider switching.
"""

import streamlit as st
import logging
from typing import Optional, Tuple, Any
from openai import OpenAI

from google_ai_client import GoogleAIClient, ChatCompletions
from local_ai_client import create_local_client, is_ollama_running, list_available_models
from session_manager import SessionManager
from config import LocalAIConfig, GoogleAIConfig

logger = logging.getLogger(__name__)


class MockClient:
    """Mock client for when no AI provider is available."""
    
    def __init__(self, error_message: str):
        self.error_message = error_message
        self.chat = MockChatCompletions(error_message)
        
        
class MockChatCompletions:
    """Mock chat completions for error handling."""
    
    def __init__(self, error_message: str):
        self.error_message = error_message
        
    def create(self, **kwargs):
        """Mock create method that returns error response."""
        class MockResponse:
            def __init__(self, error_msg):
                self.choices = [MockChoice(error_msg)]
                
        class MockChoice:
            def __init__(self, error_msg):
                self.message = MockMessage(error_msg)
                
        class MockMessage:
            def __init__(self, error_msg):
                self.content = f"Error: {error_msg}"
                
        return MockResponse(self.error_message)


class AIClientFactory:
    """Factory for creating AI clients with graceful error handling."""
    
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.local_ai_config = LocalAIConfig()
        self.google_ai_config = GoogleAIConfig()
        
    def create_client(self, provider: str) -> Tuple[Any, str, bool]:
        """
        Create AI client for specified provider.
        
        Args:
            provider: AI provider name
            
        Returns:
            Tuple of (client, provider_name, is_successful)
        """
        if provider == "Local AI (Ollama)":
            return self._create_local_client()
        elif provider == "Google AI":
            return self._create_google_client()
        elif provider == "OpenAI":
            return self._create_openai_client()
        else:
            return self._create_fallback_client(f"Unknown provider: {provider}")
            
    def _create_local_client(self) -> Tuple[Any, str, bool]:
        """Create local AI client with error handling."""
        try:
            ollama_base_url = self.local_ai_config.BASE_URL.replace('/v1', '')
            
            if not is_ollama_running(ollama_base_url):
                return self._create_fallback_client(
                    "Ollama server not running. Please start with 'ollama serve'"
                )
            
            available_models = list_available_models(ollama_base_url)
            if not available_models:
                return self._create_fallback_client(
                    "No Ollama models found. Please install with 'ollama pull gemma2:2b'"
                )
            
            # Use selected model from session state if available, otherwise fall back to config
            model_to_use = getattr(st.session_state, 'selected_local_model', self.local_ai_config.MODEL_NAME)
            
            # Ensure the selected model is actually available
            if model_to_use not in available_models:
                model_to_use = available_models[0]  # Fall back to first available model
                # Update session state to reflect the fallback
                st.session_state.selected_local_model = model_to_use
                
            client = create_local_client(
                base_url=ollama_base_url,
                model=model_to_use
            )
            
            provider_name = f"Local AI ({model_to_use})"
            return client, provider_name, True
            
        except Exception as e:
            logger.error(f"Failed to create local AI client: {e}")
            return self._create_fallback_client(
                f"Local AI error: {str(e)}"
            )
            
    def _create_google_client(self) -> Tuple[Any, str, bool]:
        """Create Google AI client with error handling."""
        try:
            api_key = self.session_manager.get_api_key("Google AI")
            
            if not api_key:
                return self._create_fallback_client(
                    "Google AI API key not provided"
                )
                
            google_client = GoogleAIClient(api_key)
            
            # Create OpenAI-compatible wrapper
            class MockOpenAIClient:
                def __init__(self, google_client):
                    self.chat = ChatCompletions(google_client)
                    
            client = MockOpenAIClient(google_client)
            provider_name = "Google AI (Gemma 3)"
            return client, provider_name, True
            
        except Exception as e:
            logger.error(f"Failed to create Google AI client: {e}")
            return self._create_fallback_client(
                f"Google AI error: {str(e)}"
            )
            
    def _create_openai_client(self) -> Tuple[Any, str, bool]:
        """Create OpenAI client with error handling."""
        try:
            api_key = self.session_manager.get_api_key("OpenAI")
            
            if not api_key:
                return self._create_fallback_client(
                    "OpenAI API key not provided"
                )
                
            client = OpenAI(api_key=api_key)
            provider_name = "OpenAI"
            return client, provider_name, True
            
        except Exception as e:
            logger.error(f"Failed to create OpenAI client: {e}")
            return self._create_fallback_client(
                f"OpenAI error: {str(e)}"
            )
            
    def _create_fallback_client(self, error_message: str) -> Tuple[Any, str, bool]:
        """Create fallback mock client for error scenarios."""
        client = MockClient(error_message)
        provider_name = "Error (Mock Client)"
        return client, provider_name, False
        
    def get_working_client(self) -> Tuple[Any, str, bool]:
        """
        Get a working AI client, trying providers in order of preference.
        
        Returns:
            Tuple of (client, provider_name, is_successful)
        """
        # Try current selected provider first
        current_provider = st.session_state.ai_provider
        client, provider_name, success = self.create_client(current_provider)
        
        if success:
            return client, provider_name, True
            
        # If current provider fails, try others
        providers = ["Local AI (Ollama)", "Google AI", "OpenAI"]
        
        for provider in providers:
            if provider != current_provider:
                client, provider_name, success = self.create_client(provider)
                if success:
                    # Update session state to reflect working provider
                    st.session_state.ai_provider = provider
                    st.info(f"🔄 Switched to {provider} due to {current_provider} unavailability")
                    return client, provider_name, True
                    
        # If all providers fail, return the last error client
        return client, provider_name, False
