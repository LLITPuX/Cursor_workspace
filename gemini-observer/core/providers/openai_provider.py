"""
OpenAI Provider - Fallback Intelligence.

Role: Backup when Gemini hits rate limits (429).
Model: GPT-4o-mini (cost-effective, fast)
"""

import os
import logging
from typing import List, Dict, Any, Optional

from openai import AsyncOpenAI

from core.llm_interface import LLMProvider, ProviderResponse, RateLimitError


class OpenAIProvider(LLMProvider):
    """
    OpenAI GPT via official API.
    
    Used for:
    - Fallback when Gemini 429
    - Analyst stream backup
    """
    
    def __init__(self, model: str = "gpt-4o-mini", api_key: Optional[str] = None):
        self._provider_name = "openai"
        self.model = model
        
        # Get API key from param or env
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            logging.warning("OpenAIProvider: No API key provided. Will fail on first request.")
        
        self.client = AsyncOpenAI(api_key=key) if key else None
        logging.info(f"OpenAIProvider initialized: {model}")

    def get_provider_name(self) -> str:
        return self._provider_name

    async def generate_response(
        self, 
        history: List[Dict[str, Any]],
        system_prompt: Optional[str] = None
    ) -> ProviderResponse:
        """
        Generates response using OpenAI API.
        
        Raises:
            RateLimitError: When 429 rate limit exceeded
        """
        if not self.client:
            raise RuntimeError("OpenAIProvider: No API key configured")
        
        # Build messages for OpenAI format
        messages = []
        
        # Add system prompt
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add history
        for msg in history:
            role = msg.get("role")
            content = msg.get("content") or (msg.get("parts", [""])[0] if msg.get("parts") else "")
            
            # Map roles
            if role == "model":
                role = "assistant"
            if role not in ["user", "assistant", "system"]:
                continue
            
            if content:
                messages.append({"role": role, "content": content})
        
        try:
            logging.info(f"OpenAIProvider: Sending request to {self.model}")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            
            content = response.choices[0].message.content or ""
            token_usage = response.usage.total_tokens if response.usage else 0
            
            return ProviderResponse(
                content=content,
                token_usage=token_usage,
                model_name=self.model
            )
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check for rate limit errors
            if '429' in error_str or 'rate' in error_str or 'quota' in error_str:
                logging.warning(f"OpenAIProvider: Rate limit hit - {e}")
                raise RateLimitError(self._provider_name, str(e))
            
            logging.error(f"OpenAIProvider Error: {e}")
            raise e
