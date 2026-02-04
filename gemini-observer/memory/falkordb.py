from typing import List, Dict, Optional
import redis.asyncio as redis
from datetime import datetime
from .base import MemoryProvider
import json
import logging
import uuid

logger = logging.getLogger(__name__)


class FalkorDBProvider(MemoryProvider):
    """
    FalkorDB Memory Provider implementing the First Stream (Ingestion/Scribe).
    
    Graph Schema (GeminiMemory):
    - (:User)-[:AUTHORED]->(:Event:Message)
    - (:Agent)-[:GENERATED]->(:Event:Message)
    - (:Event:Message)-[:HAPPENED_IN]->(:Chat)
    - (:Event:Message)-[:HAPPENED_AT {time: "HH:MM:SS"}]->(:Day)
    - (:Event:Message)-[:NEXT]->(:Event:Message)
    - (:Chat)-[:LAST_EVENT]->(:Event:Message)
    """
    
    def __init__(self, redis_client: redis.Redis, graph_name: str = "GeminiMemory"):
        self.redis_client = redis_client
        self.graph_name = graph_name

    async def _query(self, query: str) -> list:
        """Execute a Cypher query against the graph."""
        try:
            result = await self.redis_client.execute_command("GRAPH.QUERY", self.graph_name, query)
            return result
        except Exception as e:
            logger.error(f"FalkorDB Query Error: {e}\nQuery: {query}")
            raise

    def _escape(self, text: str) -> str:
        """Escape special characters for Cypher string literals."""
        if text is None:
            return ""
        return text.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')

    async def save_user_message(
        self,
        user_telegram_id: int,
        chat_id: int,
        message_id: int,
        text: str,
        timestamp: datetime,
        author_name: str = "U"
    ) -> Optional[str]:
        """
        First Stream: Save incoming user message to graph.
        Robust version: Ensures User/Chat/Day exist via MERGE.
        """
        msg_uid = f"{chat_id}:{message_id}"
        day_date = timestamp.strftime("%Y-%m-%d")
        time_str = timestamp.strftime("%H:%M:%S")
        ts_unix = timestamp.timestamp()
        safe_text = self._escape(text)
        
        # Robust Abbreviation Logic
        # "Maks" -> "MA", "John Doe" -> "JD", "A" -> "A"
        name_parts = author_name.strip().split()
        if len(name_parts) >= 2:
            abbrev = (name_parts[0][0] + name_parts[1][0]).upper()
        elif len(name_parts) == 1 and len(name_parts[0]) > 1:
            abbrev = name_parts[0][:2].upper()
        elif len(name_parts) == 1:
            abbrev = name_parts[0][0].upper()
        else:
            abbrev = "U"
        
        query = f"""
        // Ensure User exists
        MERGE (u:User {{telegram_id: {user_telegram_id}}})
        ON CREATE SET u.id = 'user_{user_telegram_id}', u.name = '{author_name}'
        
        // Ensure Chat exists
        MERGE (c:Chat {{chat_id: {chat_id}}})
        ON CREATE SET c.id = 'chat_{chat_id}', c.name = 'Chat {chat_id}'
        
        // Ensure Day exists
        MERGE (d:Day {{date: '{day_date}'}})
        ON CREATE SET d.id = '{uuid.uuid4()}', d.name = '{timestamp.day}'
        
        // Create the Message event
        CREATE (m:Event:Message {{
            uid: '{msg_uid}',
            message_id: {message_id},
            text: '{safe_text}',
            created_at: {ts_unix},
            name: '{abbrev}'
        }})
        
        // Create relationships
        CREATE (u)-[:AUTHORED]->(m)
        CREATE (m)-[:HAPPENED_IN]->(c)
        CREATE (m)-[:HAPPENED_AT {{time: '{time_str}'}}]->(d)
        
        // Linked List: update LAST_EVENT chain safely
        WITH c, m
        OPTIONAL MATCH (c)-[last_rel:LAST_EVENT]->(prev_msg)
        DELETE last_rel
        WITH c, m, prev_msg
        FOREACH (_ IN CASE WHEN prev_msg IS NOT NULL THEN [1] ELSE [] END |
            CREATE (prev_msg)-[:NEXT]->(m)
        )
        CREATE (c)-[:LAST_EVENT]->(m)
        
        RETURN m.uid
        """
        
        try:
            result = await self._query(query)
            logger.info(f"💾 Saved user message: {msg_uid} ({abbrev})")
            return msg_uid
        except Exception as e:
            logger.error(f"Failed to save user message: {e}")
            return None

    async def save_agent_response(
        self,
        agent_telegram_id: int,
        chat_id: int,
        message_id: int,
        text: str,
        timestamp: datetime
    ) -> Optional[str]:
        """
        First Stream: Save agent's response to graph.
        
        Same as save_user_message but uses [:GENERATED] instead of [:AUTHORED].
        """
        msg_uid = f"{chat_id}:{message_id}"
        day_date = timestamp.strftime("%Y-%m-%d")
        time_str = timestamp.strftime("%H:%M:%S")
        ts_unix = timestamp.timestamp()
        safe_text = self._escape(text)
        
        # Agent abbreviation is fixed: "BS" for Bober Sikfan
        abbrev = "BS"
        
        query = f"""
        // Ensure Agent exists
        MERGE (a:Agent {{telegram_id: {agent_telegram_id}}})
        ON CREATE SET a.id = 'agent_{agent_telegram_id}', a.name = 'Agent'
        
        // Ensure Chat exists
        MERGE (c:Chat {{chat_id: {chat_id}}})
        ON CREATE SET c.id = 'chat_{chat_id}', c.name = 'Chat {chat_id}'
        
        // Ensure Day exists
        MERGE (d:Day {{date: '{day_date}'}})
        ON CREATE SET d.id = '{uuid.uuid4()}', d.name = '{timestamp.day}'
        
        // Create the Message event
        CREATE (m:Event:Message {{
            uid: '{msg_uid}',
            message_id: {message_id},
            text: '{safe_text}',
            created_at: {ts_unix},
            name: '{abbrev}'
        }})
        
        // Create relationships
        CREATE (a)-[:GENERATED]->(m)
        CREATE (m)-[:HAPPENED_IN]->(c)
        CREATE (m)-[:HAPPENED_AT {{time: '{time_str}'}}]->(d)
        
        // Linked List: update LAST_EVENT chain safely
        WITH c, m
        OPTIONAL MATCH (c)-[last_rel:LAST_EVENT]->(prev_msg)
        DELETE last_rel
        WITH c, m, prev_msg
        FOREACH (_ IN CASE WHEN prev_msg IS NOT NULL THEN [1] ELSE [] END |
            CREATE (prev_msg)-[:NEXT]->(m)
        )
        CREATE (c)-[:LAST_EVENT]->(m)
        
        RETURN m.uid
        """
        
        try:
            result = await self._query(query)
            logger.info(f"💾 Saved agent response: {msg_uid}")
            return msg_uid
        except Exception as e:
            logger.error(f"Failed to save agent response: {e}")
            return None

    async def add_message(self, role: str, content: str):
        # Create a Session node (we assume a single-user singleton for now or handle IDs via context)
        # Note: The MemoryProvider interface defined in step 1 was simple: add_message(role, content)
        # It didn't have user_id or session_id. We'll default to a global 'MAIN_SESSION' for now.
        session_id = "MAIN_SESSION"
        timestamp = datetime.now().isoformat()
        
        # Escape quotes in content to prevent Cypher injection issues in this simple string construction
        safe_content = content.replace('"', '\\"').replace("'", "\\'")
        
        query = f"""
        MERGE (s:Session {{id: '{session_id}'}})
        CREATE (e:Event {{role: '{role}', content: "{safe_content}", timestamp: '{timestamp}'}})
        CREATE (s)-[:HAS_EVENT]->(e)
        """
        
        await self.redis_client.execute_command("GRAPH.QUERY", self.graph_name, query)

    async def get_history(self, limit: int = 10) -> List[Dict[str, str]]:
        session_id = "MAIN_SESSION"
        
        query = f"""
        MATCH (s:Session {{id: '{session_id}'}})-[:HAS_EVENT]->(e:Event)
        RETURN e.role, e.content, e.timestamp
        ORDER BY e.timestamp DESC
        LIMIT {limit}
        """
        
        # Execute query
        # Response format from GRAPH.QUERY is usually [header, [rows...], stats]
        response = await self.redis_client.execute_command("GRAPH.QUERY", self.graph_name, query)
        
        # Parse response (basic structure assumption)
        # response[0] -> Header info
        # response[1] -> Result set
        # response[2] -> Query stats
        
        if not response or len(response) < 2:
            return []
            
        rows = response[1]
        history = []
        
        # RedisGraph returns data in a specific internal format.
        # usually string values are bytes.
        
        for row in rows:
            # row is [role, content, timestamp]
            # Decode bytes to strings
            role = row[0].decode('utf-8') if isinstance(row[0], bytes) else row[0]
            content = row[1].decode('utf-8') if isinstance(row[1], bytes) else row[1]
            
            history.append({"role": role, "parts": [content]})
            
        # Since we ordered by DESC (newest first) for limit, we need to reverse to return chronological order for LLM
        return list(reversed(history))

    async def get_chat_context(self, chat_id: int, limit: int = 15) -> List[Dict[str, str]]:
        """
        Fetch recent chat history for dynamic system prompt.
        Returns messages with author name and time for context building.
        
        Returns: List of dicts with 'author', 'text', 'time' keys
        """
        query = f"""
        MATCH (m:Message)-[:HAPPENED_IN]->(c:Chat {{chat_id: {chat_id}}})
        MATCH (author)-[:AUTHORED|GENERATED]->(m)
        OPTIONAL MATCH (m)-[h:HAPPENED_AT]->(d:Day)
        RETURN author.name as author, m.text as text, h.time as time, m.created_at as ts
        ORDER BY m.created_at DESC
        LIMIT {limit}
        """
        
        try:
            result = await self._query(query)
            messages = []
            
            if result and len(result) > 1:
                for row in result[1]:
                    author = row[0].decode('utf-8') if isinstance(row[0], bytes) else (row[0] or "???")
                    text = row[1].decode('utf-8') if isinstance(row[1], bytes) else (row[1] or "")
                    time = row[2].decode('utf-8') if isinstance(row[2], bytes) else (row[2] or "??:??")
                    
                    messages.append({
                        'author': author,
                        'text': text[:150],  # Truncate long messages
                        'time': time
                    })
            
            # Return in chronological order (oldest first)
            return list(reversed(messages))
            
        except Exception as e:
            logger.error(f"Failed to get chat context: {e}")
            return []

    async def log_system_event(
        self,
        event_type: str,
        source: str,
        severity: str,
        details: str,
        chat_id: int = None
    ) -> Optional[str]:
        """
        Log system event to graph as (:SystemEvent).
        
        Used by Switchboard for FALLBACK events and error logging.
        
        Args:
            event_type: "FALLBACK", "error", "alert", "notification"
            source: Provider name ("gemini", "openai", "ollama")
            severity: "critical", "warning", "info"
            details: Description of the event
            chat_id: Optional chat context
        """
        timestamp = datetime.now()
        ts_unix = timestamp.timestamp()
        event_id = f"sys_{uuid.uuid4().hex[:8]}"
        safe_details = self._escape(details)
        
        query = f"""
        CREATE (e:SystemEvent {{
            id: '{event_id}',
            type: '{event_type}',
            source: '{source}',
            severity: '{severity}',
            details: '{safe_details}',
            created_at: {ts_unix}
        }})
        RETURN e.id
        """
        
        # If chat_id provided, link to chat
        if chat_id:
            query = f"""
            CREATE (e:SystemEvent {{
                id: '{event_id}',
                type: '{event_type}',
                source: '{source}',
                severity: '{severity}',
                details: '{safe_details}',
                created_at: {ts_unix}
            }})
            WITH e
            MATCH (c:Chat {{chat_id: {chat_id}}})
            CREATE (e)-[:OCCURRED_IN]->(c)
            RETURN e.id
            """
        
        try:
            result = await self._query(query)
            logger.info(f"📊 SystemEvent logged: {event_type} ({severity}) from {source}")
            return event_id
        except Exception as e:
            logger.error(f"Failed to log system event: {e}")
            return None

    async def clear_history(self):
        query = "MATCH (n) DETACH DELETE n"
        await self.redis_client.execute_command("GRAPH.QUERY", self.graph_name, query)

