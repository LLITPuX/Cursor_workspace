"""Database connection and session management"""
import asyncpg
from typing import Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class Database:
    """Database connection manager"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Create connection pool"""
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


# Global database instance
db = Database()

