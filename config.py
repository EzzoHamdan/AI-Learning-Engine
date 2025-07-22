"""Configuration settings for the Quiz Generator application."""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class QuizConfig:
    """Quiz generation configuration."""
    MIN_QUESTIONS: int = 3
    MAX_QUESTIONS: int = 15
    DEFAULT_QUESTIONS: int = 5
    SUPPORTED_FILE_TYPES: List[str] = None
    MAX_TEXT_LENGTH: int = 10000
    SUMMARY_THRESHOLD: int = 5000  # Increased from 3000 to reduce API calls
    
    # Open-ended question configuration
    MIN_OPEN_ENDED_WORDS: int = 10
    MAX_OPEN_ENDED_WORDS: int = 200
    OPEN_ENDED_SCORING_POINTS: List[int] = None
    
    def __post_init__(self):
        if self.SUPPORTED_FILE_TYPES is None:
            self.SUPPORTED_FILE_TYPES = ["pdf", "docx", "pptx"]
        if self.OPEN_ENDED_SCORING_POINTS is None:
            self.OPEN_ENDED_SCORING_POINTS = [2, 3, 4, 5]  # Available point values


@dataclass
class OpenAIConfig:
    """OpenAI API configuration."""
    MODEL: str = "gpt-3.5-turbo"
    TEMPERATURE: float = 0.7
    SUMMARY_TEMPERATURE: float = 0.5
    MAX_TOKENS: int = 2000
    
    # Open-ended scoring configuration - still use gpt-4 for accuracy when available
    SCORING_MODEL: str = "gpt-4o-mini"  # More cost-effective than gpt-4
    SCORING_TEMPERATURE: float = 0.3
    SCORING_MAX_TOKENS: int = 500
    
    @property
    def api_key(self) -> str:
        """Get API key from environment."""
        return os.getenv("OPENAI_API_KEY", "")
    
    @property
    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)


@dataclass
class GoogleAIConfig:
    """Google AI (Gemini) API configuration."""
    CHAT_MODEL: str = "gemini-1.5-flash"  # Free tier available
    SCORING_MODEL: str = "gemini-1.5-flash"  # Same model for consistency
    TEMPERATURE: float = 0.7
    SUMMARY_TEMPERATURE: float = 0.5
    MAX_TOKENS: int = 2000
    
    # Scoring configuration
    SCORING_TEMPERATURE: float = 0.3
    SCORING_MAX_TOKENS: int = 500
    
    @property
    def api_key(self) -> str:
        """Get API key from environment."""
        return os.getenv("GOOGLE_AI_API_KEY", "")
    
    @property
    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)


@dataclass
class LocalAIConfig:
    """Local AI (Ollama) configuration with smart defaults."""
    # User-configurable settings
    MODEL_NAME: str = os.getenv("LOCAL_AI_MODEL", "gemma2:2b")
    HOST: str = os.getenv("LOCAL_AI_HOST", "127.0.0.1")
    PORT: str = os.getenv("LOCAL_AI_PORT", "11434")
    
    # Auto-generated settings
    @property
    def BASE_URL(self) -> str:
        """Auto-generate base URL from host and port."""
        return f"http://{self.HOST}:{self.PORT}/v1"
    
    # Model settings
    TEMPERATURE: float = 0.7
    SUMMARY_TEMPERATURE: float = 0.5
    MAX_TOKENS: int = 2000
    
    # Scoring configuration
    SCORING_TEMPERATURE: float = 0.3
    SCORING_MAX_TOKENS: int = 500
    
    # Context window configuration
    CONTEXT_LENGTH: int = 4096
    
    @property
    def is_available(self) -> bool:
        """Check if local AI server is available."""
        try:
            import requests
            # Health check without /v1 suffix
            health_url = f"http://{self.HOST}:{self.PORT}/api/tags"
            response = requests.get(health_url, timeout=3)
            return response.status_code == 200
        except:
            return False
    
    @property
    def is_configured(self) -> bool:
        """Local AI is considered configured if it's available."""
        return self.is_available


@dataclass  
class AppConfig:
    """Main application configuration with smart provider detection."""
    APP_TITLE: str = "📚 AI Interactive Quiz Generator"
    PAGE_ICON: str = "📚"
    LAYOUT: str = "wide"
    
    # Environment variables with sensible defaults
    DEBUG_MODE: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    @property
    def available_providers(self) -> List[str]:
        """Get list of available/configured AI providers."""
        providers = []
        
        # Check Local AI first (most user-friendly)
        local_config = LocalAIConfig()
        if local_config.is_available:
            providers.append("Local AI (Ollama)")
        
        # Check Google AI
        google_config = GoogleAIConfig()
        if google_config.is_configured:
            providers.append("Google AI")
        
        # Check OpenAI
        openai_config = OpenAIConfig()
        if openai_config.is_configured:
            providers.append("OpenAI")
        
        return providers

# Difficulty level configurations
DIFFICULTY_CONFIG: Dict[str, Dict[str, str]] = {
    "Standard": {
        "emoji": "📚", 
        "description": "University-level questions testing comprehension and analysis",
        "instructions": """
        Create university-level questions that test comprehension, analysis, and application of the material.
        Questions should be straightforward but require good understanding of the content.
        Focus on key concepts, definitions, and logical connections.
        """
    },
    "Advanced": {
        "emoji": "🎓",
        "description": "Graduate-level questions requiring critical analysis",
        "instructions": """
        Create advanced questions that require synthesis, evaluation, and critical thinking.
        Include scenario-based questions and complex problem-solving.
        Test ability to apply knowledge in new contexts.
        """
    },
    "Extreme": {
        "emoji": "🔥",
        "description": "Expert-level questions with manipulative elements and edge cases",
        "instructions": """
        Create EXTREMELY challenging questions that require critical thinking, careful reading, and deep analysis.
        Make questions manipulative and tricky - use subtle distinctions, edge cases, and nuanced interpretations.
        Include questions that test ability to identify assumptions, logical fallacies, and hidden implications.
        Use complex scenarios that require synthesis of multiple concepts.
        """
    }
}

# Scoring thresholds for different difficulty levels
SCORING_CONFIG: Dict[str, Dict[str, tuple]] = {
    "Standard": {
        "excellent": (90, "🌟 Excellent! Outstanding performance!"),
        "good": (80, "👍 Great job! Well done!"),
        "fair": (70, "👌 Good work! Room for improvement."),
        "needs_improvement": (60, "📚 Fair performance. Consider reviewing the material."),
        "default": (0, "📖 Keep studying! You'll do better next time.")
    },
    "Advanced": {
        "excellent": (85, "🏆 OUTSTANDING! Exceptional critical thinking!"),
        "good": (75, "🌟 EXCELLENT! Strong analytical skills!"),
        "fair": (65, "👍 GOOD! Solid understanding of complex concepts!"),
        "needs_improvement": (50, "📚 DEVELOPING! These are challenging questions!"),
        "default": (0, "💪 CHALLENGING! Advanced material takes time to master!")
    },
    "Extreme": {
        "excellent": (80, "🏆 LEGENDARY! You've mastered the most challenging content!"),
        "good": (70, "🌟 OUTSTANDING! Excellent performance on extreme difficulty!"),
        "fair": (60, "🔥 IMPRESSIVE! Strong performance on very challenging material!"),
        "needs_improvement": (50, "👍 SOLID! Good grasp of complex concepts!"),
        "default": (0, "💪 CHALLENGING! Don't worry - extreme questions are meant to push your limits!")
    }
}
