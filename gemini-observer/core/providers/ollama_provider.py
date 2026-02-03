import ollama
import logging
from core.llm_interface import LLMProvider
from typing import List, Dict, Any, Optional


class OllamaProvider(LLMProvider):
    def __init__(self, host: str = "http://falkordb-ollama:11434", model: str = "gemma3:4b"):
        # Initialize async client
        self.client = ollama.AsyncClient(host=host)
        self.model = model
        logging.info(f"OllamaProvider initialized with model: {model} at {host}")

    async def generate_response(
        self, 
        history: List[Dict[str, Any]], 
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generates response using Ollama with dynamic system prompt.
        
        Args:
            history: List of message dicts (can be empty if context is in system_prompt)
            system_prompt: Dynamic system prompt with chat history context
        """
        ollama_messages = []
        
        # Inject Dynamic System Prompt
        if system_prompt:
            ollama_messages.append({"role": "system", "content": system_prompt})
        
        # Add any additional history messages
        for msg in history:
            role = msg.get("role")
            # Map roles: 'model' -> 'assistant'
            if role == "model":
                role = "assistant"
            
            # Ensure valid roles for Ollama (user, assistant, system)
            if role not in ["user", "assistant", "system"]:
                continue

            # Support both 'content' (new format) and 'parts' (old format)
            content = msg.get("content") or (msg.get("parts", [""])[0] if msg.get("parts") else "")
            if content:
                ollama_messages.append({"role": role, "content": content})

        try:
            logging.info(f"OllamaProvider: Sending request to {self.model}")
            response = await self.client.chat(model=self.model, messages=ollama_messages)
            
            content = response.get('message', {}).get('content', '')
            if not content:
                logging.warning("OllamaProvider: Received empty content")
                return "⚠️ Local Cortex: Empty response received."

            return content

        except Exception as e:
            logging.error(f"OllamaProvider Error: {str(e)}")
            raise e
