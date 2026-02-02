from typing import List, Dict
import redis.asyncio as redis
from datetime import datetime
from .base import MemoryProvider
import json

class FalkorDBProvider(MemoryProvider):
    def __init__(self, redis_client: redis.Redis, graph_name: str = "agent_memory"):
        self.redis_client = redis_client
        self.graph_name = graph_name

    async def _query(self, query: str, params: dict = None):
        # We use raw redis graph.query command since we don't have the full falkordb-py client in this env yet
        # or properly configured. Using raw commands via redis-py is a safe fallback.
        
        args = [self.graph_name, query]
        if params:
            # Cypher parameters need to be handled.
            # RedisGraph expects parameters separately or embedded.
            pass
            
        return await self.redis_client.execute_command("GRAPH.QUERY", *args)

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

    async def clear_history(self):
        query = "MATCH (n) DETACH DELETE n"
        await self.redis_client.execute_command("GRAPH.QUERY", self.graph_name, query)
