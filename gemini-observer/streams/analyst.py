import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Optional, List

from config.settings import settings
from transport.queue import RedisQueue
from memory.falkordb import FalkorDBProvider
from core.switchboard import Switchboard
from core.memory.prompt_builder import GraphPromptBuilder

# Configure logging
logger = logging.getLogger(__name__)

class Analyst:
    """
    Stream 3: The Analyst (Reasoning & Strategy).
    
    Role:
    - Reads from Analyst Queue (from Thinker).
    - Analyzes Narrative Snapshot.
    - Classifies Intent (Gatekeeper Logic).
    - Formulates Plan (Strategy).
    - Saves 'Analyst Snapshot' to Graph.
    - Forwards to Coordinator Queue (Stream 4).
    """
    
    def __init__(self, redis_queue: RedisQueue, memory: FalkorDBProvider, switchboard: Switchboard, prompt_builder: GraphPromptBuilder = None):
        self.queue = redis_queue
        self.memory = memory
        self.switchboard = switchboard
        self.prompt_builder = prompt_builder
        self.running = False
        self.name = "Stream 3 (Analyst)"

    async def start(self):
        """Start the Analyst stream loop."""
        self.running = True
        logger.info(f"🕵️ {self.name} initialized and listening...")
        
        while self.running:
            try:
                # 1. Pop from Analyst Queue
                event_data = await self.queue.redis_client.blpop(settings.REDIS_QUEUE_ANALYST, timeout=1)
                if not event_data:
                    continue
                
                _, raw_data = event_data
                snapshot_data = json.loads(raw_data)
                
                logger.info(f"🕵️ Analyst received snapshot: {snapshot_data.get('id', 'unknown')}")
                
                # 2. Process: Analyze & Plan
                plan_snapshot = await self._process_snapshot(snapshot_data)
                
                # 3. Forward to Coordinator (Stream 4)
                if plan_snapshot:
                    await self.queue.redis_client.rpush(
                        settings.REDIS_QUEUE_COORDINATOR, 
                        json.dumps(plan_snapshot)
                    )
                    logger.info("➡️  Forwarded to Coordinator Queue")
                    
            except Exception as e:
                logger.error(f"❌ Analyst Error: {e}")
                await asyncio.sleep(1)

    async def _process_snapshot(self, snapshot_data: Dict) -> Optional[Dict]:
        """
        Generate Analyst Snapshot (Plan) from Narrative.
        """
        try:
            narrative = snapshot_data.get("narrative", "")
            narrative_id = snapshot_data.get("id")
            original_event = snapshot_data.get("trigger_event", {})
            author_name = original_event.get("author_name", "User")
            
            # Build Prompt from Graph
            prev_analyses = await self.memory.get_today_analyst_snapshots()
            
            if self.prompt_builder:
                prompt = await self.prompt_builder.build_analyst_prompt(
                    narrative=narrative, original_text=f"[{author_name}]: {original_event.get('text', '')}",
                    prev_analyses=prev_analyses
                )
                system_prompt = await self.prompt_builder.build_system_prompt("Analyst")
            else:
                # Legacy fallback
                from core.prompts import build_analyst_prompt
                prompt = build_analyst_prompt(narrative=narrative, original_text=original_event.get("text", ""))
                system_prompt = "You are a strategic analyst. Decide the next course of action."
            
            response = await self.switchboard.generate(
                history=[{"role": "user", "content": prompt}],
                system_prompt=system_prompt
            )
            
            analysis_text = response.content.strip()
            logger.info(f"📐 Analysis: {analysis_text[:50]}...")
            
            # Parse Decision (JSON expected from LLM or heuristic parsing)
            # For this stage, we assume the LLM returns a structured thought or we parse a simple format.
            # Ideally, we want a list of tasks.
            # Example Output: "INTENT: QUESTION\nTASKS: [SEARCH, REPLY]"
            
            # Simple heuristic parsing for MVP
            intent = "CHAT"
            tasks = ["REPLY"]
            
            if "SEARCH" in analysis_text.upper():
                intent = "QUESTION"
                tasks = ["SEARCH", "REPLY"]
            elif "IGNORE" in analysis_text.upper():
                intent = "IGNORE"
                tasks = []
            
            # Save Analyst Snapshot to Graph
            analyst_snapshot_id = await self.memory.save_analyst_snapshot(
                narrative_id=narrative_id,
                analysis=analysis_text,
                intent=intent,
                tasks=tasks,
                timestamp=datetime.now()
            )
            
            if not analyst_snapshot_id:
                return None
                
            # Create Plan Object
            plan_data = {
                "type": "analyst_snapshot",
                "id": analyst_snapshot_id,
                "analysis": analysis_text,
                "intent": intent,
                "tasks": tasks,
                "original_event": original_event,
                "timestamp": datetime.now().isoformat()
            }
            
            # If intent is IGNORE, we might still want to log it but NOT forward to Coordinator?
            # Or forward with empty task list?
            if intent == "IGNORE":
                logger.info("🛑 Analyst decided to IGNORE.")
                return None
                
            return plan_data

        except Exception as e:
            logger.error(f"❌ Failed to process snapshot in Analyst: {e}")
            return None

    async def stop(self):
        self.running = False
        logger.info(f"🕵️ {self.name} stopped.")
