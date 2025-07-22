"""Google AI (Gemma 3) client wrapper for quiz generation."""

from typing import Dict, List
from google import genai
from config import GoogleAIConfig

class GoogleAIClient:
    """Wrapper for Google AI (Gemma 3) API to maintain compatibility with OpenAI interface."""
    
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.config = GoogleAIConfig()
    
    def chat_completions_create(self, model: str, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 2000):
        """Create a chat completion using Google AI API in OpenAI-compatible format."""
        try:
            # Convert OpenAI format messages to Google AI format
            # For now, we'll just use the user message content
            user_content = ""
            for message in messages:
                if message["role"] == "user":
                    user_content = message["content"]
                    break
            
            if not user_content:
                raise ValueError("No user message found in the request")
            
            # Map OpenAI models to Gemma models
            model_mapping = {
                "gpt-3.5-turbo": self.config.CHAT_MODEL,
                "gpt-4": self.config.SCORING_MODEL
            }
            
            gemma_model = model_mapping.get(model, self.config.CHAT_MODEL)
            
            print(f"DEBUG: Using model: {gemma_model}")
            print(f"DEBUG: User content length: {len(user_content)}")
            
            response = self.client.models.generate_content(
                model=gemma_model,
                contents=user_content,
            )
            
            if not response or not response.text:
                raise Exception("Empty response from Google AI API, please check your API key, credit and model configuration.")

            print(f"DEBUG: Response length: {len(response.text)}")
            
            # Return in OpenAI-compatible format
            return MockResponse(response.text)
            
        except Exception as e:
            # Log the error for debugging
            print(f"ERROR in Google AI client: {str(e)}")
            print(f"ERROR type: {type(e).__name__}")
            
            # Also show in Streamlit if available
            try:
                import streamlit as st
                st.error(f"Google AI API error: {str(e)}")
            except:
                pass

            raise Exception(f"Google AI API error: {str(e)}")


class MockResponse:
    """Mock response object to maintain OpenAI API compatibility."""
    
    def __init__(self, content: str):
        self.choices = [MockChoice(content)]


class MockChoice:
    """Mock choice object for OpenAI compatibility."""
    
    def __init__(self, content: str):
        self.message = MockMessage(content)


class MockMessage:
    """Mock message object for OpenAI compatibility."""
    
    def __init__(self, content: str):
        self.content = content


class ChatCompletions:
    """Mock chat completions class for OpenAI compatibility."""
    
    def __init__(self, client: GoogleAIClient):
        self.client = client
        self.completions = CompletionsHandler(client)
    
    def create(self, **kwargs):
        return self.client.chat_completions_create(**kwargs)


class CompletionsHandler:
    """Handler for completions.create() calls."""
    
    def __init__(self, client: GoogleAIClient):
        self.client = client
    
    def create(self, **kwargs):
        return self.client.chat_completions_create(**kwargs)
