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
from core.prompts import (
    build_system_prompt, 
    history_to_messages, 
    format_chat_history,
    RELEVANCE_FILTER_PROMPT,
    CONTEXT_STRATEGY_PROMPT
)
from transport.queue import RedisQueue

# ... (imports remain)

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
        
        # Primary provider (OpenAI GPT-4o-mini) - STABILITY FIRST
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            primary_provider = OpenAIProvider(model="gpt-4o-mini", api_key=openai_key)
        else:
            logging.warning("No OPENAI_API_KEY. Using Ollama as primary.")
            primary_provider = fast_provider

        # Fallback provider (Gemini 2.0 Flash) - FREE TIER / RATE LIMIT PRONE
        try:
            fallback_provider = GeminiProvider(model_name="gemini-2.0-flash")
        except FileNotFoundError as e:
            logging.warning(f"GeminiProvider init failed: {e}. using Ollama as fallback.")
            fallback_provider = fast_provider
        
        # Initialize Switchboard with graph logger
        self.switchboard = Switchboard(
            primary=primary_provider,
            fallback=fallback_provider,
            fast=fast_provider,
            graph_logger=memory  # FalkorDB with log_system_event()
        )
        
        logging.info("RalphLoop initialized with Switchboard (Hybrid Pipeline)")

    def set_researcher(self, researcher):
        """Inject Researcher for Agentic RAG."""
        self.researcher = researcher

    async def run_worker(self):
        """
        Infinite loop to process events from the incoming queue.
        Implements Interactive RAG: Filter -> Strategy -> Execution.
        """
        self.running = True
        logging.info("🚀 Starting RalphLoop Worker with Interactive RAG Pipeline...")
        
        while self.running:
            try:
                # Step 0: Dequeue
                event = await self.queue.pop_incoming()
                if not event:
                    await asyncio.sleep(0.1)
                    continue
                
                logging.info(f"📥 Processing event: {event.get('message_id')}")
                
                # Extract event data
                user_id = event.get("user_id")
                chat_id = event.get("chat_id")
                text = event.get("text")
                if not text:
                    continue

                # Fetch recent chat history from graph
                chat_messages = await self.memory.get_chat_context(chat_id, limit=10)
                history = history_to_messages(chat_messages)
                history_str = format_chat_history(chat_messages)

                # ════════════════════════════════════════════════════════════════
                # STEP 1: GATEKEEPER (Relevance Filter)
                # ════════════════════════════════════════════════════════════════
                filter_prompt = RELEVANCE_FILTER_PROMPT.format(
                    history=history_str,
                    message=text
                )
                
                # Use Switchboard (OPENAI by default) for logical decision
                filter_response = await self.switchboard.generate(
                    history=[{"role": "user", "content": filter_prompt}],
                    use_fast=False # Use smart model for logic
                )
                decision = filter_response.content.strip().upper()
                
                logging.info(f"🛡️ Gatekeeper Decision: {decision}")
                
                if "NO" in decision and "YES" not in decision:
                    logging.info("🛑 Logic: Ignoring message (not relevant)")
                    continue

                # ════════════════════════════════════════════════════════════════
                # STEP 2: CONTEXT STRATEGY (History vs Search)
                # ════════════════════════════════════════════════════════════════
                strategy_prompt = CONTEXT_STRATEGY_PROMPT.format(
                    history=history_str,
                    message=text
                )
                
                strategy_response = await self.switchboard.generate(
                    history=[{"role": "user", "content": strategy_prompt}],
                    use_fast=False 
                )
                strategy = strategy_response.content.strip().upper()
                
                logging.info(f"🧠 Strategy Decision: {strategy}")
                
                rag_context = ""
                
                # ════════════════════════════════════════════════════════════════
                # STEP 3: RESEARCH (Execution)
                # ════════════════════════════════════════════════════════════════
                if "SEARCH" in strategy and hasattr(self, 'researcher') and self.researcher:
                    logging.info("🔎 Strategy: Initiating Graph Search...")
                    try:
                        rag_result = await self.researcher.query_knowledge(text)
                        rag_context = f"\n\n[ЗНАЙДЕНО В БАЗІ ЗНАНЬ]:\n{rag_result}\n"
                        logging.info(f"📂 RAG Context Added: {len(rag_result)} chars")
                    except Exception as e:
                        logging.error(f"RAG Error: {e}")
                
                # ════════════════════════════════════════════════════════════════
                # STEP 4: GENERATION (Final Response)
                # ════════════════════════════════════════════════════════════════
                
                system_prompt = build_system_prompt()
                
                # Inject RAG context into the last message if exists
                if rag_context:
                    # Modify the last message in history to include found facts
                    # Or append as system instruction
                     system_prompt += rag_context
                
                try:
                    # Main Generation call
                    response: ProviderResponse = await self.switchboard.generate(
                        history=history,
                        system_prompt=system_prompt,
                        use_fast=False 
                    )
                    
                    response_text = response.content
                    logging.info(
                        f"✅ Response from {response.model_name} "
                        f"({response.token_usage} tokens)"
                    )
                    
                except Exception as e:
                    error_msg = f"⚠️ Critical: Generation failed. ({e})"
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
