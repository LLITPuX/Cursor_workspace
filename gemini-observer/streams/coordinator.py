import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Optional

from config.settings import settings
from transport.queue import RedisQueue
from core.memory.falkordb import FalkorDBProvider
from core.switchboard import Switchboard

# Configure logging
logger = logging.getLogger(__name__)

class Coordinator:
    """
    Stream 4: The Coordinator (Execution & Conducting).
    
    Role:
    - Reads from Coordinator Queue (from Analyst).
    - Executes Tasks (Tools/Action).
    - For now, it mostly handles "SEARCH" via Researcher or "REPLY" pass-through.
    - Aggregates Context.
    - Forwards to Responder Queue (Stream 5).
    """
    
    def __init__(self, redis_queue: RedisQueue, memory: FalkorDBProvider, researcher=None):
        self.queue = redis_queue
        self.memory = memory
        self.researcher = researcher # Optional tool
        self.running = False
        self.name = "Stream 4 (Coordinator)"

    async def start(self):
        """Start the Coordinator stream loop."""
        self.running = True
        logger.info(f"⚡ {self.name} initialized and listening...")
        
        while self.running:
            try:
                # 1. Pop from Coordinator Queue
                event_data = await self.queue.redis_client.blpop(settings.REDIS_QUEUE_COORDINATOR, timeout=1)
                if not event_data:
                    continue
                
                _, raw_data = event_data
                plan_snapshot = json.loads(raw_data)
                
                logger.info(f"⚡ Coordinator received plan: {plan_snapshot.get('id', 'unknown')}")
                
                # 2. Process: Execute Tasks
                context_result = await self._execute_plan(plan_snapshot)
                
                # 3. Forward to Responder (Stream 5)
                if context_result:
                    await self.queue.redis_client.rpush(
                        settings.REDIS_QUEUE_RESPONDER, 
                        json.dumps(context_result)
                    )
                    logger.info("➡️  Forwarded to Responder Queue")
                    
            except Exception as e:
                logger.error(f"❌ Coordinator Error: {e}")
                await asyncio.sleep(1)

    async def _execute_plan(self, plan: Dict) -> Optional[Dict]:
        """
        Execute tasks defined in the Analyst Snapshot.
        """
        try:
            tasks = plan.get("tasks", [])
            original_event = plan.get("original_event", {})
            intent = plan.get("intent", "CHAT")
            
            rag_context = ""
            
            # Execute "SEARCH" Task
            if "SEARCH" in tasks and self.researcher:
                query_text = original_event.get("text", "")
                logger.info(f"🔍 Coordinator executing SEARCH for: {query_text[:30]}...")
                try:
                    rag_result = await self.researcher.query_knowledge(query_text)
                    if rag_result:
                        rag_context = f"\n\n[ЗНАЙДЕНО В БАЗІ ЗНАНЬ]:\n{rag_result}\n"
                        logger.info(f"📂 RAG Context Found: {len(rag_result)} chars")
                except Exception as e:
                    logger.error(f"⚠️ Search failed: {e}")
            
            # Prepare Context for Responder
            context_summary = f"Intent: {intent}. Tasks: {tasks}"
            if rag_context:
                context_summary += f" RAG: {len(rag_context)} chars found."
            
            # Save Coordinator Snapshot to Graph (closes the thought chain)
            analyst_id = plan.get("id", "")
            coord_snapshot_id = await self.memory.save_coordinator_snapshot(
                analyst_id=analyst_id,
                context_summary=context_summary,
                tasks_executed=tasks,
                timestamp=datetime.now()
            )
            
            # We wrap the original event + added context
            context_data = {
                "type": "coordinator_context",
                "original_event": original_event,
                "plan_id": plan.get("id"),
                "coordinator_snapshot_id": coord_snapshot_id,
                "intent": intent,
                "rag_context": rag_context,
                "tasks_executed": tasks,
                "timestamp": datetime.now().isoformat()
            }
            
            return context_data

        except Exception as e:
            logger.error(f"❌ Failed to execute plan in Coordinator: {e}")
            return None

    async def stop(self):
        self.running = False
        logger.info(f"⚡ {self.name} stopped.")
