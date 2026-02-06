import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Optional

from config.settings import settings
from transport.queue import RedisQueue
from memory.falkordb import FalkorDBProvider

# Configure logging
logger = logging.getLogger(__name__)

class Scribe:
    """
    Stream 1: The Scribe
    
    Role:
    - Ingests raw events from Redis Queue (Incoming).
    - Validates data.
    - Saves to FalkorDB (Single Source of Truth).
    - Forwards to Brain Queue (Stream 2).
    """
    
    def __init__(self, redis_queue: RedisQueue, memory: FalkorDBProvider):
        self.queue = redis_queue
        self.memory = memory
        self.running = False
        self.processed_count = 0

    async def start(self):
        """Start the Scribe stream loop."""
        self.running = True
        logger.info("📜 Stream 1: Scribe initialized and listening...")
        
        while self.running:
            try:
                # 1. Pop from Incoming Queue
                event = await self.queue.pop_incoming(timeout=2)
                if not event:
                    continue
                
                logger.info(f"📜 Scribe received event: {event.get('message_id', 'unknown')}")
                
                # 2. Process & Persist
                success = await self._process_event(event)
                
                # 3. Forward to Brain (if successfully saved)
                if success:
                    await self.queue.redis_client.rpush(settings.REDIS_QUEUE_BRAIN, json.dumps(event))
                    logger.info("➡️  Forwarded to Brain Queue")
                    
            except Exception as e:
                logger.error(f"❌ Scribe Error: {e}")
                await asyncio.sleep(1)

    async def _process_event(self, event: Dict) -> bool:
        """
        Save event to FalkorDB with proper graph connections.
        Returns True if saved successfully.
        """
        try:
            # Validate required fields
            if not all(k in event for k in ["user_id", "chat_id", "text", "timestamp"]):
                logger.warning(f"⚠️  Skipping invalid event: {event}")
                return False

            user_id = event["user_id"]
            chat_id = event["chat_id"]
            text = event["text"]
            msg_id = event.get("message_id", 0)
            
            # Parse timestamp if string
            ts = event["timestamp"]
            if isinstance(ts, str):
                try:
                    timestamp = datetime.fromisoformat(ts)
                except ValueError:
                    timestamp = datetime.now()
            else:
                timestamp = datetime.now() # Fallback

            # Determine Author Name (Best Effort)
            # In a real scenario, we might need a User Profile lookup here.
            # For now, we use a placeholder or data from event if available.
            author_name = event.get("author_name", "User")
            
            # Save to Graph
            # note: FalkorDBProvider.save_user_message handles the logic
            # We assume it's a User message for now. 
            # TODO: Handle Bot messages if they come through this queue (Feedback Loop)
            
            # Check if it's a bot message (self-feedback)
            is_bot = str(user_id) == str(settings.BOT_TELEGRAM_ID)
            
            if is_bot:
                 await self.memory.save_agent_response(
                    agent_telegram_id=user_id,
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=text,
                    timestamp=timestamp
                )
            else:
                await self.memory.save_user_message(
                    user_telegram_id=user_id,
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=text,
                    timestamp=timestamp,
                    author_name=author_name
                )
            
            self.processed_count += 1
            return True

        except Exception as e:
            logger.error(f"❌ Failed to save event to Graph: {e}")
            return False

    async def stop(self):
        self.running = False
        logger.info("📜 Scribe stopped.")
