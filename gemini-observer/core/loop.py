"""
RalphLoop - Main Decision Loop with Switchboard Integration.

OODA Loop: Observe -> Orient -> Decide -> Act
Now powered by Hybrid Cognitive Pipeline with automatic Fallback.
"""

import asyncio
import logging
import os
from typing import Optional

from memory.base import MemoryProvider
from core.llm_interface import LLMProvider, ProviderResponse
from core.providers.gemini_provider import GeminiProvider
from core.providers.ollama_provider import OllamaProvider
from core.providers.openai_provider import OpenAIProvider
from core.switchboard import Switchboard
from core.prompts import build_system_prompt, history_to_messages
from transport.queue import RedisQueue


class RalphLoop:
    """
    The main decision loop of the agent (OODA Loop).
    
    Observe -> Orient -> Decide -> Act
    
    Now uses Switchboard for:
    - Automatic Fallback (Gemini -> OpenAI -> Ollama)
    - Graph logging of system events
    """
    
    def __init__(self, memory: MemoryProvider, client: GeminiProvider, queue: RedisQueue):
        # Note: 'client' argument kept for backward compatibility
        self.memory = memory
        self.queue = queue
        self.running = False
        
        # ═══════════════════════════════════════════════════════════════════
        # HYBRID COGNITIVE PIPELINE SETUP
        # ═══════════════════════════════════════════════════════════════════
        
        # Fast provider (local Gemma 3:4b)
        fast_provider = OllamaProvider(
            host="http://falkordb-ollama:11434", 
            model="gemma3:4b"
        )
        
        # Primary provider (Gemini 2.0 Flash)
        try:
            primary_provider = GeminiProvider(model_name="gemini-2.0-flash")
        except FileNotFoundError as e:
            logging.warning(f"GeminiProvider init failed: {e}. Using Ollama as primary.")
            primary_provider = fast_provider
        
        # Fallback provider (OpenAI GPT-4o-mini)
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            fallback_provider = OpenAIProvider(model="gpt-4o-mini", api_key=openai_key)
        else:
            logging.warning("No OPENAI_API_KEY. Fallback will use Ollama.")
            fallback_provider = fast_provider
        
        # Initialize Switchboard with graph logger
        self.switchboard = Switchboard(
            primary=primary_provider,
            fallback=fallback_provider,
            fast=fast_provider,
            graph_logger=memory  # FalkorDB with log_system_event()
        )
        
        logging.info("RalphLoop initialized with Switchboard (Hybrid Pipeline)")

    async def run_worker(self):
        """
        Infinite loop to process events from the incoming queue.
        """
        self.running = True
        logging.info("🚀 Starting RalphLoop Worker with Hybrid Cognitive Pipeline...")
        
        while self.running:
            try:
                # Step 0: Dequeue
                event = await self.queue.pop_incoming()
                if not event:
                    await asyncio.sleep(0.1)
                    continue
                
                logging.info(f"📥 Processing event: {event.get('message_id')}")
                
                user_id = event.get("user_id")
                chat_id = event.get("chat_id")
                text = event.get("text")
                
                if not text:
                    continue

                # ════════════════════════════════════════════════════════════════
                # BUILD CONTEXT: System Prompt + Chat History
                # ════════════════════════════════════════════════════════════════
                
                system_prompt = build_system_prompt()
                
                # Fetch recent chat history from graph
                chat_messages = await self.memory.get_chat_context(chat_id, limit=10)
                history = history_to_messages(chat_messages)
                
                logging.info(f"📚 Context: {len(history)} messages from history")
                
                # ════════════════════════════════════════════════════════════════
                # DECIDE & ACT: Generate response via Switchboard
                # ════════════════════════════════════════════════════════════════
                
                try:
                    response: ProviderResponse = await self.switchboard.generate(
                        history=history,
                        system_prompt=system_prompt,
                        use_fast=False  # Use primary->fallback chain
                    )
                    
                    response_text = response.content
                    logging.info(
                        f"✅ Response from {response.model_name} "
                        f"({response.token_usage} tokens)"
                    )
                    
                except Exception as e:
                    error_msg = f"⚠️ Critical: All providers failed. ({e})"
                    logging.error(error_msg)
                    response_text = error_msg

                # ════════════════════════════════════════════════════════════════
                # RESPOND: Enqueue outgoing message
                # ════════════════════════════════════════════════════════════════
                
                outgoing_event = {
                    "chat_id": chat_id,
                    "text": response_text,
                    "original_message_id": event.get("message_id")
                }
                await self.queue.push_outgoing(outgoing_event)
                
            except Exception as e:
                logging.error(f"❌ Error in RalphLoop: {e}")
                await asyncio.sleep(1)

    async def stop(self):
        self.running = False
        logging.info("RalphLoop stopped")
