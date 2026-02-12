import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Optional

from config.settings import settings
from transport.queue import RedisQueue
from memory.falkordb import FalkorDBProvider
from core.switchboard import Switchboard
from core.prompts import build_system_prompt, history_to_messages

# Configure logging
logger = logging.getLogger(__name__)

class Responder:
    """
    Stream 5: The Responder (Articulation).
    
    Role:
    - Reads from Responder Queue (from Coordinator).
    - Generates Final Response using Switchboard.
    - Applies Persona (Bober Sikfan).
    - Forwards to Outgoing Queue (to TelegramSender).
    - Loops back to Ingestion Queue (Self-correction/Feedback) - TODO.
    """
    
    def __init__(self, redis_queue: RedisQueue, memory: FalkorDBProvider, switchboard: Switchboard):
        self.queue = redis_queue
        self.memory = memory
        self.switchboard = switchboard
        self.running = False
        self.name = "Stream 5 (Responder)"

    async def start(self):
        """Start the Responder stream loop."""
        self.running = True
        logger.info(f"🗣️ {self.name} initialized and listening...")
        
        while self.running:
            try:
                # 1. Pop from Responder Queue
                event_data = await self.queue.redis_client.blpop(settings.REDIS_QUEUE_RESPONDER, timeout=1)
                if not event_data:
                    continue
                
                _, raw_data = event_data
                context_data = json.loads(raw_data)
                
                logger.info(f"🗣️ Responder received context: {context_data.get('plan_id', 'unknown')}")
                
                # 2. Process: Generate Response
                response_event = await self._generate_response(context_data)
                
                # 3. Forward to Outgoing Queue (TelegramSender)
                if response_event:
                    await self.queue.push_outgoing(response_event)
                    logger.info("➡️  Forwarded to Outgoing Queue")
                    
            except Exception as e:
                logger.error(f"❌ Responder Error: {e}")
                await asyncio.sleep(1)

    async def _generate_response(self, context: Dict) -> Optional[Dict]:
        """
        Generate final response text.
        """
        try:
            original_event = context.get("original_event", {})
            rag_context = context.get("rag_context", "")
            intent = context.get("intent", "CHAT")
            
            # If intent is IGNORE, we might skip generation?
            # But usually we reach here if we decided to REPLY.
            # Analyst handles IGNORE by not sending or flagging it.
            # If we are here, we should probably reply.
            
            chat_id = original_event.get("chat_id")
            
            # Fetch Conversation History for Chat context
            chat_history = await self.memory.get_chat_context(chat_id, limit=10)
            messages = history_to_messages(chat_history)
            
            # Build System Prompt
            system_prompt = build_system_prompt(chat_history)
            
            # Inject RAG Context
            if rag_context:
                system_prompt += rag_context
                
            # Call LLM
            response = await self.switchboard.generate(
                history=messages,
                system_prompt=system_prompt
            )
            
            response_text = response.content
            logger.info(f"🗣️ Generated Response: {response_text[:50]}...")
            
            # Construct Outgoing Event
            outgoing_event = {
                "chat_id": chat_id,
                "text": response_text,
                "original_message_id": original_event.get("message_id")
            }
            
            return outgoing_event

        except Exception as e:
            logger.error(f"❌ Failed to generate response: {e}")
            return None

    async def stop(self):
        self.running = False
        logger.info(f"🗣️ {self.name} stopped.")
