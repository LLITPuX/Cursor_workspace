"""
Ollama Provider - Local Cortex (fast).

Role: Fast responses, Gatekeeper filter, system notifications.
Model: Gemma 3:4b (12 tok/s)
"""

import ollama
import logging
from core.llm_interface import LLMProvider, ProviderResponse
from typing import List, Dict, Any, Optional


class OllamaProvider(LLMProvider):
    """
    Local LLM via Ollama. Used for:
    - Fast chat responses
    - Gatekeeper binary classification
    - System error notifications
    """
    
    def __init__(self, host: str = "http://falkordb-ollama:11434", model: str = "gemma3:4b"):
        self.client = ollama.AsyncClient(host=host)
        self.model = model
        self._provider_name = "ollama"
        logging.info(f"OllamaProvider initialized: {model} @ {host}")

    def get_provider_name(self) -> str:
        return self._provider_name

    async def generate_response(
        self, 
        history: List[Dict[str, Any]], 
        system_prompt: Optional[str] = None
    ) -> ProviderResponse:
        """
        Generates response using Ollama with dynamic system prompt.
        
        Returns ProviderResponse with token_usage from eval_count.
        """
        ollama_messages = []
        
        # Inject Dynamic System Prompt
        if system_prompt:
            ollama_messages.append({"role": "system", "content": system_prompt})
        
        # Add history messages
        for msg in history:
            role = msg.get("role")
            # Map roles: 'model' -> 'assistant'
            if role == "model":
                role = "assistant"
            
            # Ensure valid roles for Ollama
            if role not in ["user", "assistant", "system"]:
                continue

            # Support both 'content' (new) and 'parts' (old) format
            content = msg.get("content") or (msg.get("parts", [""])[0] if msg.get("parts") else "")
            if content:
                ollama_messages.append({"role": role, "content": content})

        try:
            logging.info(f"OllamaProvider: Sending request to {self.model}")
            response = await self.client.chat(model=self.model, messages=ollama_messages)
            
            content = response.get('message', {}).get('content', '')
            if not content:
                logging.warning("OllamaProvider: Received empty content")
                content = "⚠️ Local Cortex: Empty response received."

            # Extract token usage from response
            token_usage = response.get('eval_count', 0)
            
            return ProviderResponse(
                content=content,
                token_usage=token_usage,
                model_name=self.model
            )

        except Exception as e:
            logging.error(f"OllamaProvider Error: {str(e)}")
            raise e
