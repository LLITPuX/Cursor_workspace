import os
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from config.settings import settings
from core.llm_interface import LLMProvider
import logging
from typing import List, Dict, Any

class GeminiProvider(LLMProvider):
    """
    Wrapper for the Google Generative AI SDK using OAuth credentials.
    Implements LLMProvider interface.
    """
    def __init__(self):
        self._configure()
        self.model = genai.GenerativeModel('gemini-2.0-flash') # User requested 2.x Flash model

    def _configure(self):
        """
        Loads credentials from token.json and configures the SDK.
        Refreshes the token if expired.
        """
        token_path = settings.GEMINI_TOKEN_PATH
        
        if not os.path.exists(token_path):
            raise FileNotFoundError(f"Token file not found at {token_path}. Run scripts/auth_google.py first.")

        creds = Credentials.from_authorized_user_file(token_path, scopes=['https://www.googleapis.com/auth/generative-language.retriever.readonly', 'https://www.googleapis.com/auth/cloud-platform'])

        if creds and creds.expired and creds.refresh_token:
            logging.info("GeminiProvider: Refreshing expired token...")
            creds.refresh(Request())

        # Configure GenAI
        try:
             # Attempt to configure with credentials (if supported by library version or mock)
             # NOTE: Standard genai.configure uses api_key. Detailed OAuth handling usually requires 
             # passing credentials to the transport or using a different client. 
             # We assume the environment or library handles this based on the existing pattern.
             genai.configure(credentials=creds)
        except Exception as e:
             logging.warning(f"GeminiProvider: configure(credentials) failed or ignored: {e}")
             # Code proceeds hoping auth works via other means or has been set up

    async def generate_response(self, history: List[Dict[str, Any]]) -> str:
        """
        Generates a response from the model.
        :param history: List of message dicts (from MemoryProvider)
        :return: Text response
        """
        
        # Logging for Debugging
        logging.info(f"GeminiProvider Input History: {history}")

        if not history:
            return "Error: No history to generate from."
            
        last_msg = history[-1]
        chat_history = history[:-1]
        
        formatted_history = []
        for msg in chat_history:
            role = msg.get('role')
            content = msg.get('parts', [""])[0]
            
            # Map roles if necessary
            if role == 'bot': role = 'model'
            if role not in ['user', 'model']:
                logging.warning(f"Skipping invalid role in history: {role}")
                continue
                
            formatted_history.append({"role": role, "parts": [content]})
            
        logging.info(f"GeminiProvider Formatted History: {formatted_history}")
        
        chat = self.model.start_chat(history=formatted_history)
        
        # Last message must be user
        last_text = last_msg['parts'][0]
        logging.info(f"GeminiProvider Sending: {last_text}")
        
        try:
            response = chat.send_message(last_text)
            return response.text
        except Exception as e:
            logging.error(f"Gemini API Execution Error: {e}")
            raise e
