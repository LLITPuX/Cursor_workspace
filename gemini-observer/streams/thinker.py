import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Optional

from config.settings import settings
from transport.queue import RedisQueue
from memory.falkordb import FalkorDBProvider
from core.switchboard import Switchboard
from core.memory.prompt_builder import GraphPromptBuilder

# Configure logging
logger = logging.getLogger(__name__)

class Thinker:
    """
    Stream 2: The Thinker (Intuition & Narrative).
    
    Role:
    - Reads from Brain Queue (from Scribe).
    - Checks Agent State (Busy/Idle).
    - Generates 'Narrative Snapshot' using LLM (What is happening?).
    - Saves Snapshot to Graph.
    - Forwards to Analyst Queue (Stream 3).
    """
    
    def __init__(self, redis_queue: RedisQueue, memory: FalkorDBProvider, switchboard: Switchboard, prompt_builder: GraphPromptBuilder = None):
        self.queue = redis_queue
        self.memory = memory
        self.switchboard = switchboard
        self.prompt_builder = prompt_builder
        self.running = False
        self.name = "Stream 2 (Thinker)"

    async def start(self):
        """Start the Thinker stream loop."""
        self.running = True
        logger.info(f"🧠 {self.name} initialized and listening...")
        
        while self.running:
            try:
                # 1. Pop from Brain Queue (Ingested Events)
                event_data = await self.queue.redis_client.blpop(settings.REDIS_QUEUE_BRAIN, timeout=1)
                if not event_data:
                    continue
                
                # blpop returns (key, value) tuple
                _, raw_event = event_data
                event = json.loads(raw_event)
                
                logger.info(f"🧠 Thinker received event: {event.get('message_id', 'unknown')}")
                
                # 2. Process: Generate Narrative
                snapshot = await self._process_event(event)
                
                # 3. Forward to Analyst (Stream 3) via Redis
                # We forward the Snapshot content, not just the raw event
                if snapshot:
                    await self.queue.redis_client.rpush(
                        settings.REDIS_QUEUE_ANALYST, 
                        json.dumps(snapshot)
                    )
                    logger.info("➡️  Forwarded to Analyst Queue")
                    
            except Exception as e:
                logger.error(f"❌ Thinker Error: {e}")
                await asyncio.sleep(1)

    async def _process_event(self, event: Dict) -> Optional[Dict]:
        """
        Generate Narrative Snapshot from Event.
        """
        try:
            # Check Agent State (Are we busy?)
            # For now, we assume simple processing. 
            # TODO: Implement Lock State check via Graph.
            
            # Prepare Context for LLM
            text = event.get("text", "")
            user_id = event.get("user_id")
            chat_id = event.get("chat_id")
            msg_uid = event.get("uid") # Graph UID if available, or construct it
            
            if not msg_uid:
                # Reconstruct UID if not passed (though Scribe should pass it)
                # This is fallback.
                 msg_uid = f"{chat_id}:{event.get('message_id')}"

            # Build Prompt from Graph
            chat_context = await self.memory.get_chat_context(chat_id, limit=5)
            
            if self.prompt_builder:
                prompt = await self.prompt_builder.build_narrative_prompt(
                    current_message=text, chat_history=chat_context
                )
                system_prompt = await self.prompt_builder.build_system_prompt("Thinker")
            else:
                # Legacy fallback
                from core.prompts import build_narrative_prompt
                prompt = build_narrative_prompt(current_message=text, chat_history=chat_context)
                system_prompt = "You are the inner voice of an AI. Analyze the situation briefly."
            
            response = await self.switchboard.generate(
                history=[{"role": "user", "content": prompt}],
                system_prompt=system_prompt
            )
            
            narrative_text = response.content.strip()
            logger.info(f"💭 Narrative: {narrative_text[:50]}...")
            
            # Save Snapshot to Graph
            snapshot_id = await self.memory.save_narrative_snapshot(
                event_uid=msg_uid,
                narrative=narrative_text,
                timestamp=datetime.now()
            )
            
            if not snapshot_id:
                logger.error("Failed to save narrative snapshot.")
                return None
                
            # Create Snapshot Object to pass forward
            snapshot_data = {
                "type": "narrative_snapshot",
                "id": snapshot_id,
                "narrative": narrative_text,
                "trigger_event": event,
                "timestamp": datetime.now().isoformat()
            }
            
            return snapshot_data

        except Exception as e:
            logger.error(f"❌ Failed to process event in Thinker: {e}")
            return None

    async def stop(self):
        self.running = False
        logger.info(f"🧠 {self.name} stopped.")
