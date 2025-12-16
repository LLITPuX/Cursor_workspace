"""Database connection and session management"""
import asyncpg
import json
from typing import Optional, List
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class Database:
    """Database connection manager"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Create connection pool"""
        if not settings.neon_connection_string:
            logger.warning("NEON_CONNECTION_STRING not set, database features will be disabled")
            return
        
        try:
            self.pool = await asyncpg.create_pool(
                settings.neon_connection_string,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
            logger.info("Database connection pool created")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise
    
    async def disconnect(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    async def execute(self, query: str, *args):
        """Execute a query"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args):
        """Fetch rows"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args):
        """Fetch single row"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def create_session(self, topic: Optional[str] = None, metadata: Optional[dict] = None) -> str:
        """Create a new session and return its ID"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            # Convert dict to JSON string for asyncpg JSONB
            metadata_json = json.dumps(metadata or {})
            row = await conn.fetchrow(
                """
                INSERT INTO sessions (topic, metadata)
                VALUES ($1, $2::jsonb)
                RETURNING id
                """,
                topic,
                metadata_json
            )
            return str(row['id'])
    
    async def save_message(
        self, 
        session_id: str, 
        role: str, 
        content: str, 
        embedding: Optional[List[float]] = None
    ) -> str:
        """Save a message with optional embedding and return message ID"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            # Convert embedding list to pgvector format string
            embedding_str = None
            if embedding:
                # Format: '[0.1,0.2,0.3]' for pgvector
                embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'
            
            row = await conn.fetchrow(
                """
                INSERT INTO messages (session_id, role, content, embedding_v2)
                VALUES ($1, $2, $3, $4::vector)
                RETURNING id
                """,
                session_id,
                role,
                content,
                embedding_str
            )
            return str(row['id'])


# Global database instance
db = Database()

