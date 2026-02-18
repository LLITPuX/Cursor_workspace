"""
Gemini Provider - Primary Cloud Intelligence.

Role: Main analytical engine for complex tasks.
Model: Gemini 2.0 Flash (via OAuth)
Fallback: OpenAI when 429 rate limit hit
"""

import os
import logging
from typing import List, Dict, Any, Optional

import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from config.settings import settings
from core.llm_interface import LLMProvider, ProviderResponse, RateLimitError


class GeminiProvider(LLMProvider):
    """
    Google Gemini via OAuth credentials.
    
    Used for:
    - Primary chat responses (when not rate-limited)
    - Analyst stream (Second Cognitive Loop)
    - Complex reasoning tasks
    """
    
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self._provider_name = "gemini"
        self.model_name = model_name
        self._configure()
        self.model = genai.GenerativeModel(model_name)
        logging.info(f"GeminiProvider initialized: {model_name}")

    def get_provider_name(self) -> str:
        return self._provider_name

    def _configure(self):
        """
        Loads credentials from token.json and configures the SDK.
        Refreshes the token if expired.
        """
        token_path = settings.GEMINI_TOKEN_PATH
        
        if not os.path.exists(token_path):
            raise FileNotFoundError(
                f"Token file not found at {token_path}. "
                "Run scripts/auth_google.py first."
            )

        creds = Credentials.from_authorized_user_file(
            token_path, 
            scopes=[
                'https://www.googleapis.com/auth/generative-language.retriever.readonly', 
                'https://www.googleapis.com/auth/cloud-platform'
            ]
        )

        if creds and creds.expired and creds.refresh_token:
            logging.info("GeminiProvider: Refreshing expired token...")
            creds.refresh(Request())

        try:
            genai.configure(credentials=creds)
        except Exception as e:
            logging.warning(f"GeminiProvider: configure(credentials) warning: {e}")

    async def generate_response(
        self, 
        history: List[Dict[str, Any]],
        system_prompt: Optional[str] = None
    ) -> ProviderResponse:
        """
        Generates response using Gemini API.
        
        Raises:
            RateLimitError: When 429 quota exceeded (triggers Switchboard fallback)
        """
        logging.info(f"GeminiProvider: Processing {len(history)} messages")

        if not history:
            return ProviderResponse(
                content="Error: No history to generate from.",
                token_usage=0,
                model_name=self.model_name
            )
        
        # Build formatted history for Gemini
        formatted_history = []
        
        # Add system instruction if provided
        # Note: Gemini uses system_instruction parameter differently
        
        for msg in history[:-1]:  # All except last
            role = msg.get('role')
            content = msg.get('content') or (msg.get('parts', [""])[0] if msg.get('parts') else "")
            
            # Map roles
            if role == 'assistant':
                role = 'model'
            if role not in ['user', 'model']:
                continue
                
            formatted_history.append({"role": role, "parts": [content]})
        
        # Last message (current user input)
        last_msg = history[-1]
        last_text = last_msg.get('content') or (last_msg.get('parts', [""])[0] if last_msg.get('parts') else "")
        
        try:
            # Create model with system instruction if provided
            model = self.model
            if system_prompt:
                model = genai.GenerativeModel(
                    self.model_name,
                    system_instruction=system_prompt,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=2048,
                        temperature=0.9
                    )
                )
            
            # Start chat with history
            chat = model.start_chat(history=formatted_history)
            
            logging.info(f"GeminiProvider: Sending message...")
            response = chat.send_message(last_text)
            
            # Extract token usage if available
            token_usage = 0
            if hasattr(response, 'usage_metadata'):
                token_usage = getattr(response.usage_metadata, 'total_token_count', 0)
            
            return ProviderResponse(
                content=response.text,
                token_usage=token_usage,
                model_name=self.model_name
            )
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check for rate limit errors (429)
            if '429' in error_str or 'quota' in error_str or 'rate' in error_str:
                logging.warning(f"GeminiProvider: Rate limit hit - {e}")
                raise RateLimitError(self._provider_name, str(e))
            
            logging.error(f"GeminiProvider Error: {e}")
            raise e
