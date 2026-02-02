from abc import ABC, abstractmethod
from typing import List, Dict, Any

class LLMProvider(ABC):
    """
    Abstract Interface for LLM Providers (Gemini, Ollama, etc.)
    """
    @abstractmethod
    async def generate_response(self, history: List[Dict[str, Any]]) -> str:
        """
        Generate a text response based on the conversation history.
        :param history: List of message dictionaries [{'role': 'user/model', 'parts': ['text']}]
        :return: Generated text
        """
        pass
