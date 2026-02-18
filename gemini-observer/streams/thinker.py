import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Optional

from config.settings import settings
from transport.queue import RedisQueue
from core.memory.falkordb import FalkorDBProvider
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
        Perform Semantic Analysis on Event.
        """
        try:
            # Check Agent State (Are we busy?)
            # TODO: Implement Lock State check via Graph.
            
            # Prepare Data
            text = event.get("text", "")
            chat_id = event.get("chat_id")
            author_name = event.get("author_name", "User")
            msg_uid = event.get("uid")
            
            if not msg_uid:
                 msg_uid = f"{chat_id}:{event.get('message_id')}"

            # 1. Fetch Rich Context from Graph
            chat_context = await self.memory.get_chat_context(chat_id, limit=5)
            active_topics = await self.memory.get_active_topics()
            entity_types = await self.memory.get_entity_types()
            recent_thoughts = await self.memory.get_recent_thinker_responses()
            weekly_summaries = await self.memory.get_weekly_summaries()
            
            # 2. Build Prompt
            if self.prompt_builder:
                prompt = await self.prompt_builder.build_narrative_prompt(
                    current_message=f"[{author_name}]: {text}", 
                    chat_history=chat_context, 
                    active_topics=active_topics,
                    entity_types=entity_types,
                    recent_thougths=recent_thoughts,
                    weekly_summaries=weekly_summaries
                )
                system_prompt = await self.prompt_builder.build_system_prompt("Thinker") # Fallback if not inside build_narrative_prompt
            else:
                logger.error("❌ GraphPromptBuilder not initialized in Thinker!")
                return None
            
            # 3. Call LLM (Meta-Cognition)
            response = await self.switchboard.generate(
                history=[{"role": "user", "content": prompt}],
                system_prompt="" # System prompt is already built into 'prompt' by build_narrative_prompt logic logic, or we can pass it separately.
                # prompt_builder.build_narrative_prompt returns (system + user). 
                # Switchboard might handle this. Let's assume passed as ONE prompt for now, or split.
                # Actually build_narrative_prompt returns the FULL prompt. 
                # Switchboard needs system_prompt separated usually.
                # Let's check prompt_builder again. It returns `system + "\n\n" + user`.
                # So here we should probably pass empty system_prompt, or refactor prompt_builder to return tuple.
                # For now, I will treat the whole thing as user prompt with empty system, or rely on model to handle it.
                # Better: Split it manually or just pass it all.
            )
            
            raw_response = response.content.strip()
            # Cleanup Markdown ```json ... ```
            if "```json" in raw_response:
                raw_response = raw_response.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_response:
                raw_response = raw_response.split("```")[1].split("```")[0].strip()

            # 4. Log to ThinkerLogs (Async)
            await self.memory.save_thinker_log(
                prompt=prompt,
                response=raw_response,
                model="gemini"
            )

            # 5. Parse JSON
            try:
                analysis_data = json.loads(raw_response)
            except json.JSONDecodeError:
                logger.error(f"❌ Thinker failed to parse JSON: {raw_response}")
                return None

            logger.info(f"💭 Thought: {analysis_data.get('summary', 'No summary')}")
            
            # 6. Push to Enrichment Queue (Stream 1 Sidecar)
            # We add the msg_uid to map it back
            analysis_data['target_message_uid'] = msg_uid
            # TODO: Implement queue push in the main loop or here. 
            # We don't have the enrichment queue in settings yet, let's assume 'redis:enrichment_queue'
            await self.queue.redis_client.rpush('redis:enrichment_queue', json.dumps(analysis_data))
            
            # 7. Create Narrative Snapshot for Stream 3 (Analyst)
            # Analyst expects 'narrative' and 'trigger_event'
            narrative_text = analysis_data.get('summary', text) # Fallback to text if summary missing
            
            snapshot_id = await self.memory.save_narrative_snapshot(
                event_uid=msg_uid,
                narrative=narrative_text,
                timestamp=datetime.now()
            )
            
            snapshot_data = {
                "type": "narrative_snapshot",
                "id": snapshot_id,
                "narrative": narrative_text,
                "trigger_event": event,
                "timestamp": datetime.now().isoformat(),
                "semantic_data": analysis_data # Pass full data to Analyst too!
            }
            
            return snapshot_data

        except Exception as e:
            logger.error(f"❌ Failed to process event in Thinker: {e}")
            return None

    async def stop(self):
        self.running = False
        logger.info(f"🧠 {self.name} stopped.")
