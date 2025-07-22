"""
Local AI client for running Gemma models locally using Ollama.
Provides OpenAI-compatible interface for local model inference.
"""

import requests
import json
import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Choice:
    """Mock OpenAI choice object for local AI responses."""
    message: object
    index: int = 0
    finish_reason: str = "stop"


@dataclass
class Message:
    """Mock OpenAI message object for local AI responses."""
    content: str
    role: str = "assistant"


@dataclass 
class CompletionResponse:
    """Mock OpenAI completion response object."""
    choices: List[Choice]
    id: str = "local-completion"
    created: int = 0
    model: str = ""
    
    def __post_init__(self):
        if self.created == 0:
            self.created = int(time.time())


class LocalAIClient:
    """Client for interacting with local AI models via Ollama API."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "gemma2:2b"):
        """
        Initialize local AI client.
        
        Args:
            base_url: Base URL for Ollama API (default: http://127.0.0.1:11434)
            model: Model name to use (default: gemma2:2b)
        """
        self.base_url = base_url.rstrip('/').replace('/v1', '')  # Remove /v1 suffix if present
        self.model = model
        self.timeout = 120  # Longer timeout for local inference
        
        # Check if Ollama is running
        if not self.is_available():
            raise ConnectionError(f"Ollama server not available at {self.base_url}")
        
        # Ensure model is available
        self._ensure_model_available()
    
    def is_available(self) -> bool:
        """Check if Ollama server is running."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return False
    
    def _ensure_model_available(self) -> None:
        """Ensure the specified model is available, pull if necessary."""
        try:
            # Check available models
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [model['name'] for model in models]
                
                if self.model not in model_names:
                    logger.info(f"Model {self.model} not found locally. Pulling...")
                    self._pull_model()
                else:
                    logger.info(f"Model {self.model} is available locally")
            else:
                logger.warning(f"Could not check available models: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error checking model availability: {e}")
            raise
    
    def _pull_model(self) -> None:
        """Pull the specified model if not available."""
        try:
            pull_data = {"name": self.model}
            response = requests.post(
                f"{self.base_url}/api/pull",
                json=pull_data,
                stream=True,
                timeout=300  # 5 minutes for model download
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully initiated pull for model {self.model}")
                # Stream the response to show progress
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if 'status' in data:
                                logger.info(f"Pull status: {data['status']}")
                        except json.JSONDecodeError:
                            continue
            else:
                raise Exception(f"Failed to pull model: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error pulling model {self.model}: {e}")
            raise
    
    def generate_completion(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False
    ) -> CompletionResponse:
        """
        Generate completion using local AI model.
        
        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream response (not implemented)
            
        Returns:
            CompletionResponse object mimicking OpenAI format
        """
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('response', '').strip()
                
                # Create mock OpenAI response structure
                message = Message(content=content)
                choice = Choice(message=message)
                
                return CompletionResponse(
                    choices=[choice],
                    model=self.model
                )
            else:
                raise Exception(f"Local AI request failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error in local AI completion: {e}")
            raise
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> CompletionResponse:
        """
        Generate chat completion using local AI model.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            CompletionResponse object mimicking OpenAI format
        """
        # Convert messages to a single prompt
        prompt_parts = []
        for message in messages:
            role = message.get('role', 'user')
            content = message.get('content', '')
            
            if role == 'system':
                prompt_parts.append(f"System: {content}")
            elif role == 'user':
                prompt_parts.append(f"User: {content}")
            elif role == 'assistant':
                prompt_parts.append(f"Assistant: {content}")
        
        prompt_parts.append("Assistant:")
        full_prompt = "\n".join(prompt_parts)
        
        return self.generate_completion(full_prompt, temperature, max_tokens)


class LocalChatCompletions:
    """Chat completions interface compatible with OpenAI client."""
    
    def __init__(self, local_client: LocalAIClient):
        self.local_client = local_client
    
    def create(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> CompletionResponse:
        """Create chat completion using local AI."""
        max_tokens = max_tokens or 2000
        return self.local_client.chat_completion(messages, temperature, max_tokens)


class LocalChat:
    """Chat interface that contains completions, matching OpenAI API structure."""
    
    def __init__(self, local_client: LocalAIClient):
        self.completions = LocalChatCompletions(local_client)


class MockLocalOpenAIClient:
    """Mock OpenAI client that uses local AI backend."""
    
    def __init__(self, local_client: LocalAIClient):
        self.chat = LocalChat(local_client)
        self.local_client = local_client
    
    @property
    def model_name(self) -> str:
        """Get the current model name."""
        return self.local_client.model


def create_local_client(base_url: str = "http://127.0.0.1:11434", model: str = "gemma2:2b") -> MockLocalOpenAIClient:
    """
    Create a local AI client with OpenAI-compatible interface.
    
    Args:
        base_url: Ollama server URL
        model: Model name to use
        
    Returns:
        MockLocalOpenAIClient instance
    """
    local_client = LocalAIClient(base_url, model)
    return MockLocalOpenAIClient(local_client)


# Utility functions for model management
def list_available_models(base_url: str = "http://127.0.0.1:11434") -> List[str]:
    """List all available models on the Ollama server."""
    try:
        # Ensure we remove any /v1 suffix for API call
        clean_url = base_url.rstrip('/').replace('/v1', '')
        response = requests.get(f"{clean_url}/api/tags", timeout=10)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return [model['name'] for model in models]
        return []
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        return []


def download_model(model_name: str, base_url: str = "http://127.0.0.1:11434") -> bool:
    """Download a model to the local Ollama server."""
    try:
        # Ensure we remove any /v1 suffix for API call
        clean_url = base_url.rstrip('/').replace('/v1', '')
        pull_data = {"name": model_name}
        response = requests.post(
            f"{clean_url}/api/pull",
            json=pull_data,
            timeout=600  # 10 minutes for large models
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error downloading model {model_name}: {e}")
        return False


def is_ollama_running(base_url: str = "http://127.0.0.1:11434") -> bool:
    """Check if Ollama server is running."""
    try:
        # Ensure we remove any /v1 suffix for health check
        clean_url = base_url.rstrip('/').replace('/v1', '')
        response = requests.get(f"{clean_url}/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False
