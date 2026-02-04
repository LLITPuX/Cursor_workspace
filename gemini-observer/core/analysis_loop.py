"""
Cognitive Loop - Second Stream Analysis.

This module implements the Second Stream of the Hybrid Cognitive Pipeline:
1. Gatekeeper (local Gemma) - Filters 90% of messages with binary classification
2. Analyst (Gemini/OpenAI) - Deep analysis of important messages
3. Researcher (optional) - Agentic RAG for search queries

Architecture:
- Runs as background worker
- Listens to Redis queue 'analysis:queue'
- Writes results to FalkorDB as (:Thought) nodes
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

import redis.asyncio as redis

from core.llm_interface import ProviderResponse
from core.switchboard import Switchboard


@dataclass
class AnalysisResult:
    """Result of message analysis by Analyst."""
    topic: str
    target_user: Optional[str]
    new_facts: list[str]
    search_query: Optional[str]
    raw_response: str


class CognitiveLoop:
    """
    Second Stream: Background analysis of chat messages.
    
    Flow:
    1. Message arrives in 'analysis:queue'
    2. Gatekeeper (Gemma) decides: needs analysis? (1/0)
    3. If yes → Analyst (Gemini/OpenAI) extracts structured data
    4. If search_query exists → Researcher queries Knowledge Graph
    5. Result saved to FalkorDB as (:Thought) node
    """
    
    # Gatekeeper prompt for binary classification
    GATEKEEPER_PROMPT = """Ти — Фільтр Повідомлень. Твоя задача — визначити, чи потребує це повідомлення глибокого аналізу для оновлення Графа Знань.

Відповідай ТІЛЬКИ одним символом: 1 (так, потребує) або 0 (ні, не потребує).

Критерії для 1 (потребує аналізу):
- Містить нову фактичну інформацію про людину/подію
- Містить важливе запитання або прохання
- Описує плани, цілі, стосунки
- Містить технічну інформацію

Критерії для 0 (НЕ потребує):
- Просте привітання (привіт, ок, дякую)
- Стікери, емодзі
- Однослівні відповіді
- Повторення вже відомої інформації

Повідомлення для аналізу:
"""

    # Analyst prompt for structured extraction
    ANALYST_PROMPT = """Ти — Аналітик Знань. Проаналізуй повідомлення та витягни структуровану інформацію.

Поверни відповідь у форматі JSON (без markdown):
{
  "topic": "коротка тема повідомлення",
  "target_user": "ім'я користувача якого стосується інформація, або null",
  "new_facts": ["факт 1", "факт 2"],
  "search_query": "запит для пошуку в базі знань, або null"
}

Правила:
- topic: 2-5 слів, основна тема
- target_user: тільки якщо явно згадується людина
- new_facts: тільки нова інформація, без очевидного
- search_query: тільки якщо користувач шукає інформацію

Повідомлення:
"""

    def __init__(
        self,
        redis_client: redis.Redis,
        switchboard: Switchboard,
        memory_provider,  # FalkorDBProvider
        researcher=None,  # Optional Researcher for agentic RAG
        queue_in: str = "analysis:queue",
        queue_deep: str = "analysis:deep_queue"
    ):
        self.redis = redis_client
        self.switchboard = switchboard
        self.memory = memory_provider
        self.researcher = researcher
        self.queue_in = queue_in
        self.queue_deep = queue_deep
        self.running = False
        
        logging.info(f"CognitiveLoop initialized (researcher={'enabled' if researcher else 'disabled'})")

    async def start(self):
        """Start both Gatekeeper and Analyst workers."""
        self.running = True
        logging.info("🧠 Starting Cognitive Loop (Second Stream)...")
        
        await asyncio.gather(
            self._gatekeeper_worker(),
            self._analyst_worker()
        )

    async def stop(self):
        """Stop the cognitive loop."""
        self.running = False
        logging.info("CognitiveLoop stopped")

    async def enqueue_message(self, message_data: Dict[str, Any]):
        """Add message to analysis queue."""
        await self.redis.lpush(
            self.queue_in, 
            json.dumps(message_data, ensure_ascii=False)
        )
        logging.debug(f"Enqueued message for analysis: {message_data.get('message_id')}")

    # ═══════════════════════════════════════════════════════════════════════
    # GATEKEEPER - Local Gemma Binary Classification
    # ═══════════════════════════════════════════════════════════════════════
    
    async def _gatekeeper_worker(self):
        """
        Gatekeeper worker: Uses local Gemma to filter messages.
        
        Economy: ~90% of messages are filtered out, saving cloud API costs.
        """
        logging.info("🚧 Gatekeeper worker started")
        
        while self.running:
            try:
                # Block for message with 1 second timeout
                result = await self.redis.brpop(self.queue_in, timeout=1)
                
                if not result:
                    continue
                
                _, raw_data = result
                message_data = json.loads(raw_data)
                text = message_data.get("text", "")
                
                if not text or len(text) < 3:
                    logging.debug(f"Gatekeeper: Skipping short message")
                    continue
                
                # Ask Gemma: needs analysis?
                prompt = self.GATEKEEPER_PROMPT + text
                
                response: ProviderResponse = await self.switchboard.generate(
                    history=[{"role": "user", "content": prompt}],
                    system_prompt=None,
                    use_fast=True  # Force Ollama/Gemma
                )
                
                decision = response.content.strip()
                
                # Parse binary decision
                needs_analysis = decision.startswith("1")
                
                logging.info(
                    f"🚧 Gatekeeper: '{text[:30]}...' → {decision} "
                    f"({'PASS' if needs_analysis else 'SKIP'})"
                )
                
                if needs_analysis:
                    # Pass to deep analysis queue
                    await self.redis.lpush(
                        self.queue_deep,
                        json.dumps(message_data, ensure_ascii=False)
                    )
                    
            except Exception as e:
                logging.error(f"Gatekeeper error: {e}")
                await asyncio.sleep(1)

    # ═══════════════════════════════════════════════════════════════════════
    # ANALYST - Gemini/OpenAI Deep Analysis
    # ═══════════════════════════════════════════════════════════════════════
    
    async def _analyst_worker(self):
        """
        Analyst worker: Uses Gemini/OpenAI for deep analysis.
        
        Extracts structured data and saves as (:Thought) node in graph.
        """
        logging.info("🔬 Analyst worker started")
        
        while self.running:
            try:
                # Block for message with 1 second timeout
                result = await self.redis.brpop(self.queue_deep, timeout=1)
                
                if not result:
                    continue
                
                _, raw_data = result
                message_data = json.loads(raw_data)
                text = message_data.get("text", "")
                chat_id = message_data.get("chat_id")
                message_id = message_data.get("message_id")
                user_id = message_data.get("user_id")
                
                # Ask Gemini/OpenAI for structured analysis
                prompt = self.ANALYST_PROMPT + text
                
                response: ProviderResponse = await self.switchboard.generate(
                    history=[{"role": "user", "content": prompt}],
                    system_prompt=None,
                    use_fast=False  # Use primary (Gemini) → fallback (OpenAI)
                )
                
                # Parse JSON response
                analysis = self._parse_analysis(response.content)
                
                if analysis:
                    logging.info(
                        f"🔬 Analyst: topic='{analysis.topic}', "
                        f"facts={len(analysis.new_facts)}, "
                        f"model={response.model_name}"
                    )
                    
                    # ═══════════════════════════════════════════════════════
                    # RESEARCHER - Agentic RAG
                    # ═══════════════════════════════════════════════════════
                    if analysis.search_query and self.researcher:
                        logging.info(f"🔎 Invoking Researcher for: {analysis.search_query}")
                        try:
                            graph_answer = await self.researcher.query_knowledge(analysis.search_query)
                            # Add findings to facts so they are saved in Thought
                            analysis.new_facts.append(f"Graph Research: {graph_answer}")
                        except Exception as e:
                            logging.error(f"Researcher failed: {e}")
                    
                    # Save to graph as (:Thought) node
                    await self._save_thought(
                        chat_id=chat_id,
                        message_id=message_id,
                        user_id=user_id,
                        analysis=analysis,
                        model_used=response.model_name
                    )
                else:
                    logging.warning(f"Analyst: Failed to parse response for message {message_id}")
                    
            except Exception as e:
                logging.error(f"Analyst error: {e}")
                await asyncio.sleep(1)

    def _parse_analysis(self, response_text: str) -> Optional[AnalysisResult]:
        """Parse JSON response from Analyst."""
        try:
            # Clean response (remove markdown if present)
            text = response_text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            
            data = json.loads(text)
            
            return AnalysisResult(
                topic=data.get("topic", "unknown"),
                target_user=data.get("target_user"),
                new_facts=data.get("new_facts", []),
                search_query=data.get("search_query"),
                raw_response=response_text
            )
        except (json.JSONDecodeError, KeyError) as e:
            logging.warning(f"Failed to parse analysis JSON: {e}")
            return None

    async def _save_thought(
        self,
        chat_id: int,
        message_id: int,
        user_id: int,
        analysis: AnalysisResult,
        model_used: str
    ):
        """Save analysis result as (:Thought) node in FalkorDB."""
        if not hasattr(self.memory, '_query'):
            logging.warning("Memory provider doesn't support _query")
            return
        
        import uuid
        from datetime import datetime
        
        thought_id = f"thought_{uuid.uuid4().hex[:8]}"
        msg_uid = f"{chat_id}:{message_id}"
        ts_unix = datetime.now().timestamp()
        
        # Escape strings
        safe_topic = self.memory._escape(analysis.topic)
        safe_facts = self.memory._escape(json.dumps(analysis.new_facts, ensure_ascii=False))
        safe_query = self.memory._escape(analysis.search_query or "")
        safe_target = self.memory._escape(analysis.target_user or "")
        
        query = f"""
        // Find source message
        MATCH (m:Message {{uid: '{msg_uid}'}})
        
        // Create Thought node
        CREATE (t:Thought {{
            id: '{thought_id}',
            topic: '{safe_topic}',
            target_user: '{safe_target}',
            new_facts: '{safe_facts}',
            search_query: '{safe_query}',
            model_used: '{model_used}',
            created_at: {ts_unix}
        }})
        
        // Link Thought to Message
        CREATE (t)-[:DERIVED_FROM]->(m)
        
        RETURN t.id
        """
        
        try:
            await self.memory._query(query)
            logging.info(f"💭 Saved Thought: {thought_id} for message {msg_uid}")
        except Exception as e:
            logging.error(f"Failed to save Thought: {e}")
