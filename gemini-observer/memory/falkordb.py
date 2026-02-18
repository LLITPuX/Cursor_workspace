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

    # Static mapping for known authors (Telegram ID -> Abbreviation)
    AUTHOR_ABBREV = {
        298085237: "MA",      # Maks
        5561942654: "YU",     # Yulianna
        8521381973: "BS",     # Bober Sikfan (Agent)
    }

    def __init__(self, redis_client: redis.Redis, graph_name: str = None):
        self.redis_client = redis_client
        from config.settings import settings
        self.graph_name = graph_name or settings.FALKORDB_GRAPH_NAME

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

    async def _get_next_message_name(self, author_id: int, day_date: str, telegram_author_name: str = "") -> str:
        """
        Generate the next message name in strict format {ABBREV}{SEQ:02d}.
        
        Args:
            author_id: Telegram User ID
            day_date: Date string "YYYY-MM-DD"
            telegram_author_name: Author name for fallback abbreviation generation
        """
        # 1. Determine Abbreviation
        abbrev = self.AUTHOR_ABBREV.get(author_id)
        
        # Fallback if not in static mapping
        if not abbrev:
            name_parts = telegram_author_name.strip().split()
            if len(name_parts) >= 2:
                abbrev = (name_parts[0][0] + name_parts[1][0]).upper()
            elif len(name_parts) == 1 and len(name_parts[0]) > 1:
                abbrev = name_parts[0][:2].upper()
            elif len(name_parts) == 1:
                abbrev = name_parts[0][0].upper()
            else:
                abbrev = "U"
        
        # 2. Count existing messages for this author on this day
        query = f"""
        MATCH (d:Day {{date: '{day_date}'}})
        MATCH (m:Message)-[:HAPPENED_AT]->(d)
        MATCH (author)-[:AUTHORED|GENERATED]->(m)
        WHERE author.telegram_id = {author_id}
        RETURN count(m)
        """
        try:
            result = await self._query(query)
            # Result format: [[count]]
            count = result[1][0][0] if result and result[1] else 0
            # Ensure count is int (RedisGraph might return float or string depending on client)
            if isinstance(count, bytes):
                count = int(float(count.decode('utf-8')))
            else:
                count = int(count)
        except Exception as e:
            logger.warning(f"Failed to count messages for naming, starting at 0: {e}")
            count = 0
            
        # 3. Generate Name (next sequence)
        seq = count + 1
        return f"{abbrev}{seq:02d}"

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
        
        # Generate Strict Name
        node_name = await self._get_next_message_name(user_telegram_id, day_date, author_name)
        
        query = f"""
        // Ensure User exists and update metadata
        MERGE (u:User {{telegram_id: {user_telegram_id}}})
        ON CREATE SET u.id = 'user_{user_telegram_id}', u.name = '{author_name}'
        ON MATCH SET u.name = '{author_name}'
        
        // Ensure Chat exists
        MERGE (c:Chat {{chat_id: {chat_id}}})
        ON CREATE SET c.id = 'chat_{chat_id}', c.name = 'Chat {chat_id}'
        
        // Ensure Day and Year exist with MONTH relationship
        MERGE (d:Day {{date: '{day_date}'}})
        ON CREATE SET d.id = '{uuid.uuid4()}', d.name = '{timestamp.day}'
        MERGE (y:Year {{value: {timestamp.year}}})
        MERGE (y)-[:MONTH {{number: {timestamp.month}}}]->(d)
        
        // Create the Message event
        CREATE (m:Event:Message {{
            uid: '{msg_uid}',
            message_id: {message_id},
            text: '{safe_text}',
            created_at: {ts_unix},
            name: '{node_name}'
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
            logger.info(f"💾 Saved user message: {msg_uid} ({node_name})")
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
        
        # Agent Name
        node_name = await self._get_next_message_name(agent_telegram_id, day_date, "Bober Sikfan")
        
        query = f"""
        // Ensure Agent exists
        MERGE (a:Agent {{telegram_id: {agent_telegram_id}}})
        ON CREATE SET a.id = 'agent_{agent_telegram_id}', a.name = 'Agent'
        
        // Ensure Chat exists
        MERGE (c:Chat {{chat_id: {chat_id}}})
        ON CREATE SET c.id = 'chat_{chat_id}', c.name = 'Chat {chat_id}'
        
        // Ensure Day and Year exist with MONTH relationship
        MERGE (d:Day {{date: '{day_date}'}})
        ON CREATE SET d.id = '{uuid.uuid4()}', d.name = '{timestamp.day}'
        MERGE (y:Year {{value: {timestamp.year}}})
        MERGE (y)-[:MONTH {{number: {timestamp.month}}}]->(d)
        
        // Create the Message event
        CREATE (m:Event:Message {{
            uid: '{msg_uid}',
            message_id: {message_id},
            text: '{safe_text}',
            created_at: {ts_unix},
            name: '{node_name}'
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
            logger.info(f"💾 Saved agent response: {msg_uid} ({node_name})")
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

    async def save_narrative_snapshot(
        self,
        event_uid: str,
        narrative: str,
        timestamp: datetime
    ) -> Optional[str]:
        """
        Stream 2: Save Narrative Snapshot linked to a Message Event.
        """
        snapshot_id = f"snap_narrative_{uuid.uuid4().hex[:8]}"
        ts_unix = timestamp.timestamp()
        safe_narrative = self._escape(narrative)
        
        query = f"""
        MATCH (m:Event:Message {{uid: '{event_uid}'}})
        CREATE (s:Snapshot:Narrative {{
            id: '{snapshot_id}',
            content: '{safe_narrative}',
            created_at: {ts_unix}
        }})
        CREATE (m)-[:TRIGGERED]->(s)
        RETURN s.id
        """
        
        try:
            result = await self._query(query)
            logger.info(f"🧠 Saved Narrative Snapshot: {snapshot_id}")
            return snapshot_id
        except Exception as e:
            logger.error(f"Failed to save narrative snapshot: {e}")
            return None

    async def save_analyst_snapshot(
        self,
        narrative_id: str,
        analysis: str,
        intent: str,
        tasks: List[str],
        timestamp: datetime
    ) -> Optional[str]:
        """
        Stream 3: Save Analyst Snapshot linked to a Narrative.
        """
        snapshot_id = f"snap_analyst_{uuid.uuid4().hex[:8]}"
        ts_unix = timestamp.timestamp()
        safe_analysis = self._escape(analysis)
        tasks_json = json.dumps(tasks).replace('"', '\\"') # Simple escape
        
        query = f"""
        MATCH (n:Snapshot:Narrative {{id: '{narrative_id}'}})
        CREATE (a:Snapshot:Analyst {{
            id: '{snapshot_id}',
            analysis: '{safe_analysis}',
            intent: '{intent}',
            tasks: "{tasks_json}",
            created_at: {ts_unix}
        }})
        CREATE (n)-[:LED_TO]->(a)
        RETURN a.id
        """
        
        try:
            result = await self._query(query)
            logger.info(f"🕵️ Saved Analyst Snapshot: {snapshot_id}")
            return snapshot_id
        except Exception as e:
            logger.error(f"Failed to save analyst snapshot: {e}")
            return None

    async def save_coordinator_snapshot(
        self,
        analyst_id: str,
        context_summary: str,
        tasks_executed: List[str],
        timestamp: datetime
    ) -> Optional[str]:
        """
        Stream 4: Save Coordinator Snapshot linked to Analyst Snapshot.
        Creates the chain: Narrative → Analyst → Coordinator
        """
        snapshot_id = f"snap_coord_{uuid.uuid4().hex[:8]}"
        ts_unix = timestamp.timestamp()
        safe_summary = self._escape(context_summary)
        tasks_json = json.dumps(tasks_executed).replace('"', '\\"')
        
        query = f"""
        MATCH (a:Snapshot:Analyst {{id: '{analyst_id}'}})
        CREATE (co:Snapshot:Coordinator {{
            id: '{snapshot_id}',
            context: '{safe_summary}',
            tasks_executed: "{tasks_json}",
            created_at: {ts_unix}
        }})
        CREATE (a)-[:LED_TO]->(co)
        RETURN co.id
        """
        
        try:
            result = await self._query(query)
            logger.info(f"⚡ Saved Coordinator Snapshot: {snapshot_id}")
            return snapshot_id
        except Exception as e:
            logger.error(f"Failed to save coordinator snapshot: {e}")
            return None

    async def get_today_narrative_snapshots(self) -> List[Dict]:
        """
        Get ALL narrative snapshots for today.
        Returns list of dicts with 'id', 'content', 'created_at'.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        
        query = f"""
        MATCH (d:Day {{date: '{today}'}})
        MATCH (m:Message)-[:HAPPENED_AT]->(d)
        MATCH (m)-[:TRIGGERED]->(s:Snapshot:Narrative)
        RETURN s.id, s.content, s.created_at
        ORDER BY s.created_at ASC
        """
        
        try:
            result = await self._query(query)
            snapshots = []
            if result and len(result) > 1:
                for row in result[1]:
                    sid = row[0].decode() if isinstance(row[0], bytes) else row[0]
                    content = row[1].decode() if isinstance(row[1], bytes) else row[1]
                    ts = row[2]
                    snapshots.append({'id': sid, 'content': content, 'created_at': ts})
            return snapshots
        except Exception as e:
            logger.error(f"Failed to get today's narrative snapshots: {e}")
            return []

    async def get_today_analyst_snapshots(self) -> List[Dict]:
        """
        Get ALL analyst snapshots for today.
        Returns list of dicts with 'id', 'analysis', 'intent', 'created_at'.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        
        query = f"""
        MATCH (d:Day {{date: '{today}'}})
        MATCH (m:Message)-[:HAPPENED_AT]->(d)
        MATCH (m)-[:TRIGGERED]->(:Snapshot:Narrative)-[:LED_TO]->(a:Snapshot:Analyst)
        RETURN a.id, a.analysis, a.intent, a.created_at
        ORDER BY a.created_at ASC
        """
        
        try:
            result = await self._query(query)
            snapshots = []
            if result and len(result) > 1:
                for row in result[1]:
                    sid = row[0].decode() if isinstance(row[0], bytes) else row[0]
                    analysis = row[1].decode() if isinstance(row[1], bytes) else row[1]
                    intent = row[2].decode() if isinstance(row[2], bytes) else row[2]
                    ts = row[3]
                    snapshots.append({'id': sid, 'analysis': analysis, 'intent': intent, 'created_at': ts})
            return snapshots
        except Exception as e:
            logger.error(f"Failed to get today's analyst snapshots: {e}")
            return []
    async def get_active_topics(self) -> List[Dict[str, str]]:
        """Fetch all active topics."""
        query = "MATCH (t:Topic {status: 'active'}) RETURN t.title, t.description"
        try:
            result = await self._query(query)
            topics = []
            if result and len(result) > 1:
                for row in result[1]:
                    title = row[0].decode() if isinstance(row[0], bytes) else row[0]
                    desc = row[1].decode() if isinstance(row[1], bytes) else row[1]
                    topics.append({"title": title, "description": desc})
            return topics
        except Exception as e:
            logger.error(f"Failed to get active topics: {e}")
            return []

    async def get_entity_types(self) -> List[str]:
        """Fetch all distinct entity types."""
        query = "MATCH (e:Entity) RETURN DISTINCT e.type"
        try:
            result = await self._query(query)
            types = []
            if result and len(result) > 1:
                for row in result[1]:
                    etype = row[0].decode() if isinstance(row[0], bytes) else row[0]
                    types.append(etype)
            return types
        except Exception as e:
            logger.error(f"Failed to get entity types: {e}")
            return []

    async def get_recent_thinker_responses(self, limit: int = 5) -> List[str]:
        """Fetch recent LLM responses logged in ThinkerLogs from today."""
        # Note: Querying a different graph key "ThinkerLogs"
        query = f"""
        MATCH (l:LogEntry) 
        WHERE l.timestamp > {datetime.now().timestamp() - 86400} 
        RETURN l.response 
        ORDER BY l.timestamp DESC 
        LIMIT {limit}
        """
        try:
            # We need to execute this against ThinkerLogs graph
            result = await self.redis_client.execute_command("GRAPH.QUERY", "ThinkerLogs", query)
            responses = []
            if result and len(result) > 1:
                for row in result[1]:
                    resp = row[0].decode() if isinstance(row[0], bytes) else row[0]
                    responses.append(resp)
            return responses
        except Exception as e:
            logger.warning(f"Failed to get recent thinker logs: {e}")
            return []

    async def get_weekly_summaries(self, limit: int = 7) -> List[str]:
        """Fetch day summaries for the last 7 days."""
        query = f"""
        MATCH (d:Day)<-[:SUMMARIZES]-(s:DaySummary)
        RETURN s.content
        ORDER BY d.date DESC
        LIMIT {limit}
        """
        try:
            result = await self._query(query)
            summaries = []
            if result and len(result) > 1:
                for row in result[1]:
                    content = row[0].decode() if isinstance(row[0], bytes) else row[0]
                    summaries.append(content)
            return summaries
        except Exception as e:
            logger.warning(f"Failed to get weekly summaries: {e}")
            return []

    async def save_thinker_log(self, prompt: str, response: str, model: str = "gemini"):
        """Save prompt/response pair to ThinkerLogs graph."""
        timestamp = datetime.now().timestamp()
        safe_prompt = self._escape(prompt)
        safe_response = self._escape(response)
        
        query = f"""
        CREATE (:LogEntry {{
            timestamp: {timestamp},
            prompt: '{safe_prompt}',
            response: '{safe_response}',
            model: '{model}'
        }})
        """
        try:
            await self.redis_client.execute_command("GRAPH.QUERY", "ThinkerLogs", query)
        except Exception as e:
            logger.error(f"Failed to save Thinker log: {e}")
