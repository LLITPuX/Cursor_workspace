"""
LLM Provider Interface for Hybrid Cognitive Pipeline.

Architecture:
- OllamaProvider (fast) - local Gemma 3:4b
- GeminiProvider (primary) - cloud Gemini 2.0 Flash  
- OpenAIProvider (fallback) - GPT-4o-mini

All providers MUST return ProviderResponse, not str.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class ProviderResponse:
    """
    Типізована відповідь від LLM провайдера.
    
    Attributes:
        content: Текст відповіді
        token_usage: Кількість витрачених токенів
        model_name: Назва моделі, яка відповіла
    """
    content: str
    token_usage: int
    model_name: str


class RateLimitError(Exception):
    """
    Виключення для перевищення ліміту запитів.
    Switchboard ловить це і перемикається на fallback.
    """
    def __init__(self, provider: str, message: str = "Rate limit exceeded"):
        self.provider = provider
        self.message = message
        super().__init__(f"{provider}: {message}")


class LLMProvider(ABC):
    """
    Abstract Interface for LLM Providers.
    
    Implementations:
    - OllamaProvider (fast): Local Gemma 3:4b
    - GeminiProvider (primary): Google Gemini 2.0 Flash
    - OpenAIProvider (fallback): GPT-4o-mini
    """
    
    @abstractmethod
    async def generate_response(
        self, 
        history: List[Dict[str, Any]],
        system_prompt: Optional[str] = None
    ) -> ProviderResponse:
        """
        Generate a response based on conversation history.
        
        Args:
            history: List of message dicts [{'role': 'user/assistant', 'content': '...'}]
            system_prompt: Optional system prompt for context
            
        Returns:
            ProviderResponse with content, token_usage, and model_name
            
        Raises:
            RateLimitError: When rate limit is exceeded (triggers Switchboard fallback)
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Returns the name of this provider for logging.
        
        Returns:
            Provider name (e.g., 'ollama', 'gemini', 'openai')
        """
        pass
