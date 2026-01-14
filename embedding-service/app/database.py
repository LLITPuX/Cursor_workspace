"""Database connection and session management"""
import asyncpg
import json
from typing import Optional, List, Dict, Any
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
    
    async def update_message_embedding(
        self,
        message_id: str,
        embedding: List[float]
    ) -> bool:
        """Update embedding for an existing message"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            # Convert embedding list to pgvector format string
            embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'
            
            result = await conn.execute(
                """
                UPDATE messages
                SET embedding_v2 = $1::vector
                WHERE id = $2
                """,
                embedding_str,
                message_id
            )
            return result == "UPDATE 1"
    
    async def get_messages_without_embeddings(
        self,
        limit: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> List[dict]:
        """Get all messages without embeddings_v2, optionally filtered by session_id"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            query = """
                SELECT id, session_id, role, content
                FROM messages
                WHERE embedding_v2 IS NULL
            """
            params = []
            param_num = 1
            
            if session_id:
                query += f" AND session_id = ${param_num}"
                params.append(session_id)
                param_num += 1
            
            query += " ORDER BY created_at"
            
            if limit:
                query += f" LIMIT ${param_num}"
                params.append(limit)
            
            rows = await conn.fetch(query, *params) if params else await conn.fetch(query)
            return [
                {
                    'id': str(row['id']),
                    'session_id': str(row['session_id']) if row['session_id'] else None,
                    'role': row['role'],
                    'content': row['content']
                }
                for row in rows
            ]
    
    async def session_exists(self, session_id: str) -> bool:
        """Check if session exists"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM sessions WHERE id = $1",
                session_id
            )
            return row is not None
    
    # ========== Vector Search (RAG) Functions ==========
    
    async def vector_search_messages(
        self,
        query_embedding: List[float],
        limit: int = 10,
        session_id: Optional[str] = None,
        role: Optional[str] = None,
        similarity_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search on messages
        
        Args:
            query_embedding: Query embedding vector
            limit: Maximum number of results
            session_id: Optional filter by session_id
            role: Optional filter by role ('user' or 'assistant')
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
            
        Returns:
            List of messages with similarity scores
        """
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'
            
            query = """
                SELECT 
                    id,
                    session_id,
                    role,
                    content,
                    created_at,
                    1 - (embedding_v2 <=> $1::vector) as similarity
                FROM messages
                WHERE embedding_v2 IS NOT NULL
                AND (1 - (embedding_v2 <=> $1::vector)) >= $2
            """
            params = [embedding_str, similarity_threshold]
            param_num = 3
            
            if session_id:
                query += f" AND session_id = ${param_num}"
                params.append(session_id)
                param_num += 1
            
            if role:
                query += f" AND role = ${param_num}"
                params.append(role)
                param_num += 1
            
            query += f" ORDER BY embedding_v2 <=> $1::vector LIMIT ${param_num}"
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
            return [
                {
                    'id': str(row['id']),
                    'session_id': str(row['session_id']) if row['session_id'] else None,
                    'role': row['role'],
                    'content': row['content'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'similarity': float(row['similarity'])
                }
                for row in rows
            ]
    
    async def vector_search_entity_nodes(
        self,
        query_embedding: List[float],
        types: Optional[List[str]] = None,
        limit: int = 10,
        similarity_threshold: float = 0.0,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search on entity_nodes
        
        Args:
            query_embedding: Query embedding vector
            types: Optional list of entity types to filter by
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
            active_only: Only return active nodes (valid_to IS NULL)
            
        Returns:
            List of entity nodes with similarity scores
        """
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'
            
            query = """
                SELECT 
                    id,
                    name,
                    type,
                    description,
                    created_at,
                    valid_to,
                    1 - (embedding_v2 <=> $1::vector) as similarity
                FROM entity_nodes
                WHERE embedding_v2 IS NOT NULL
                AND (1 - (embedding_v2 <=> $1::vector)) >= $2
            """
            params = [embedding_str, similarity_threshold]
            param_num = 3
            
            if active_only:
                query += f" AND valid_to IS NULL"
            
            if types:
                query += f" AND type = ANY(${param_num}::text[])"
                params.append(types)
                param_num += 1
            
            query += f" ORDER BY embedding_v2 <=> $1::vector LIMIT ${param_num}"
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
            return [
                {
                    'id': str(row['id']),
                    'name': row['name'],
                    'type': row['type'],
                    'description': row['description'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'valid_to': row['valid_to'].isoformat() if row['valid_to'] else None,
                    'similarity': float(row['similarity'])
                }
                for row in rows
            ]
    
    # ========== Entity Links Functions ==========
    
    async def create_message_entity_link(
        self,
        message_id: str,
        entity_id: str,
        relation_type: str  # 'uses', 'applies', 'executed_in'
    ) -> str:
        """
        Create a link between a message and an entity (rule/instruction/protocol)
        
        Args:
            message_id: Message UUID
            entity_id: Entity node UUID
            relation_type: Type of relation
            
        Returns:
            Link ID
        """
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO message_entity_links (message_id, entity_id, relation_type)
                VALUES ($1, $2, $3)
                ON CONFLICT (message_id, entity_id, relation_type) DO NOTHING
                RETURNING id
                """,
                message_id,
                entity_id,
                relation_type
            )
            if row:
                return str(row['id'])
            # If conflict, fetch existing link
            row = await conn.fetchrow(
                """
                SELECT id FROM message_entity_links
                WHERE message_id = $1 AND entity_id = $2 AND relation_type = $3
                """,
                message_id,
                entity_id,
                relation_type
            )
            return str(row['id']) if row else None
    
    async def create_session_entity_link(
        self,
        session_id: str,
        entity_id: str,
        relation_type: str  # 'executed_in', 'uses'
    ) -> str:
        """
        Create a link between a session and an entity
        
        Args:
            session_id: Session UUID
            entity_id: Entity node UUID
            relation_type: Type of relation
            
        Returns:
            Link ID
        """
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO session_entity_links (session_id, entity_id, relation_type)
                VALUES ($1, $2, $3)
                ON CONFLICT (session_id, entity_id, relation_type) DO NOTHING
                RETURNING id
                """,
                session_id,
                entity_id,
                relation_type
            )
            if row:
                return str(row['id'])
            # If conflict, fetch existing link
            row = await conn.fetchrow(
                """
                SELECT id FROM session_entity_links
                WHERE session_id = $1 AND entity_id = $2 AND relation_type = $3
                """,
                session_id,
                entity_id,
                relation_type
            )
            return str(row['id']) if row else None
    
    # ========== Critical Rules Functions ==========
    
    async def get_critical_rules(self) -> List[Dict[str, Any]]:
        """
        Load all critical rules from CriticalRules system node
        
        Returns:
            List of critical rules
        """
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            # Find CriticalRules node
            critical_rules_node = await conn.fetchrow(
                """
                SELECT id FROM entity_nodes
                WHERE name = 'CriticalRules'
                AND type = 'SystemNode'
                AND valid_to IS NULL
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            
            if not critical_rules_node:
                logger.warning("CriticalRules node not found")
                return []
            
            # Get all rules linked to CriticalRules
            rows = await conn.fetch(
                """
                SELECT n.id, n.name, n.description, n.type
                FROM entity_nodes n
                JOIN entity_edges e ON n.id = e.target_id
                WHERE e.source_id = $1
                AND e.relation_type = 'contains'
                AND n.type = 'Rule'
                AND n.valid_to IS NULL
                AND e.valid_to IS NULL
                ORDER BY n.name
                """,
                critical_rules_node['id']
            )
            
            return [
                {
                    'id': str(row['id']),
                    'name': row['name'],
                    'description': row['description'],
                    'type': row['type']
                }
                for row in rows
            ]
    
    async def get_entity_by_name_and_type(
        self,
        name: str,
        entity_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get entity node by name and type
        
        Args:
            name: Entity name
            entity_type: Entity type
            
        Returns:
            Entity node dict or None
        """
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, name, type, description, created_at, valid_to
                FROM entity_nodes
                WHERE name = $1 AND type = $2 AND valid_to IS NULL
                ORDER BY created_at DESC
                LIMIT 1
                """,
                name,
                entity_type
            )
            
            if not row:
                return None
            
            return {
                'id': str(row['id']),
                'name': row['name'],
                'type': row['type'],
                'description': row['description'],
                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                'valid_to': row['valid_to'].isoformat() if row['valid_to'] else None
            }
    
    async def get_entity_children(
        self,
        entity_id: str,
        relation_type: str = 'contains',
        child_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get child entities linked to a parent entity
        
        Args:
            entity_id: Parent entity UUID
            relation_type: Type of relation (default: 'contains')
            child_type: Optional filter by child type
            
        Returns:
            List of child entities
        """
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            query = """
                SELECT n.id, n.name, n.type, n.description, n.created_at, n.valid_to
                FROM entity_nodes n
                JOIN entity_edges e ON n.id = e.target_id
                WHERE e.source_id = $1
                AND e.relation_type = $2
                AND n.valid_to IS NULL
                AND e.valid_to IS NULL
            """
            params = [entity_id, relation_type]
            
            if child_type:
                query += " AND n.type = $3"
                params.append(child_type)
            
            query += " ORDER BY n.name"
            
            rows = await conn.fetch(query, *params)
            return [
                {
                    'id': str(row['id']),
                    'name': row['name'],
                    'type': row['type'],
                    'description': row['description'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'valid_to': row['valid_to'].isoformat() if row['valid_to'] else None
                }
                for row in rows
            ]
    
    # ========== Embedding Model Functions ==========
    
    async def get_active_embedding_model(self) -> Optional[Dict[str, Any]]:
        """
        Get the active embedding model
        
        Returns:
            Active embedding model dict or None
        """
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            # Check if embedding_models table exists
            table_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'embedding_models'
                )
                """
            )
            
            if not table_exists:
                logger.warning("embedding_models table does not exist. Run migration 002.")
                return None
            
            row = await conn.fetchrow(
                """
                SELECT id, name, dimension, provider, model_config
                FROM embedding_models
                WHERE is_active = TRUE
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            
            if not row:
                return None
            
            return {
                'id': str(row['id']),
                'name': row['name'],
                'dimension': row['dimension'],
                'provider': row['provider'],
                'model_config': row['model_config']
            }
    
    async def save_message_with_model(
        self,
        session_id: str,
        role: str,
        content: str,
        embedding: Optional[List[float]] = None,
        embedding_model_id: Optional[str] = None
    ) -> str:
        """
        Save a message with embedding and model reference
        
        Args:
            session_id: Session UUID
            role: Message role
            content: Message content
            embedding: Optional embedding vector
            embedding_model_id: Optional embedding model UUID
            
        Returns:
            Message ID
        """
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            embedding_str = None
            if embedding:
                embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'
            
            # Check if embedding_model_id column exists
            column_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'messages' AND column_name = 'embedding_model_id'
                )
                """
            )
            
            if column_exists and embedding_model_id:
                row = await conn.fetchrow(
                    """
                    INSERT INTO messages (session_id, role, content, embedding_v2, embedding_model_id)
                    VALUES ($1, $2, $3, $4::vector, $5)
                    RETURNING id
                    """,
                    session_id,
                    role,
                    content,
                    embedding_str,
                    embedding_model_id
                )
            else:
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

