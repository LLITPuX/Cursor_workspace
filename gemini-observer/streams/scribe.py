import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Optional

from config.settings import settings
from transport.queue import RedisQueue
from core.memory.falkordb import FalkorDBProvider

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
        
        enrichment_queue_key = "redis:enrichment_queue"
        incoming_key = self.queue.incoming_key
        
        while self.running:
            try:
                # 1. Pop from Incoming Queues (Ingest AND Enrichment)
                # Listen to both keys.
                result = await self.queue.redis_client.blpop([incoming_key, enrichment_queue_key], timeout=2)
                
                if not result:
                    continue
                
                key_bytes, value_bytes = result
                key = key_bytes.decode() if isinstance(key_bytes, bytes) else key_bytes
                value = value_bytes.decode() if isinstance(value_bytes, bytes) else value_bytes
                data = json.loads(value)

                if key == incoming_key:
                    logger.info(f"📜 Scribe received event: {data.get('message_id', 'unknown')}")
                    # 2a. Process Event (Message)
                    success = await self._process_event(data)
                    
                    # 3. Forward to Brain (Stream 2)
                    if success:
                        await self.queue.redis_client.rpush(settings.REDIS_QUEUE_BRAIN, json.dumps(data))
                        logger.info("➡️  Forwarded to Brain Queue")
                
                elif key == enrichment_queue_key:
                    logger.info(f"✨ Scribe received enrichment for: {data.get('target_message_uid', 'unknown')}")
                    # 2b. Process Enrichment (Semantic Data)
                    await self._process_enrichment(data)

            except Exception as e:
                logger.error(f"❌ Scribe Error: {e}")
                await asyncio.sleep(1)

    async def _process_enrichment(self, data: Dict):
        """
        Process semantic enrichment data from Thinker.
        """
        try:
            msg_uid = data.get('target_message_uid')
            topics = data.get('topics', [])
            entities = data.get('entities', []) # Expecting list of dicts {name, type}
            
            # If entities is list of strings (legacy/simple), normalize
            if entities and isinstance(entities[0], str):
                entities = [{'name': e, 'type': 'Concept'} for e in entities]

            if msg_uid:
                await self.memory.save_semantic_enrichment(msg_uid, topics, entities)
                logger.info(f"✅ Enriched message {msg_uid} with {len(topics)} topics & {len(entities)} entities")
        except Exception as e:
            logger.error(f"❌ Failed to process enrichment: {e}")

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
