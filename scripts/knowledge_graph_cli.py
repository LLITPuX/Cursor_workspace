#!/usr/bin/env python3
"""
CLI tool for managing the knowledge graph (rules, instructions, protocols).

This tool allows you to create, list, update, and link entities in the knowledge graph.

Usage:
    python scripts/knowledge_graph_cli.py [command] [options]
    
Commands:
    create-rule      Create a new rule
    create-instruction Create a new instruction
    create-protocol  Create a new protocol
    list             List entities by type
    link             Link two entities
    show             Show details of an entity
    search           Search entities by name/description
"""
import os
import sys
import asyncio
import asyncpg
import argparse
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KnowledgeGraphCLI:
    """CLI for managing knowledge graph."""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Create connection pool."""
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=1,
            max_size=5
        )
    
    async def close(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
    
    async def create_entity(
        self,
        name: str,
        entity_type: str,
        description: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """Create a new entity node."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO entity_nodes (name, type, description, metadata)
                VALUES ($1, $2, $3, $4::jsonb)
                RETURNING id
            """, name, entity_type, description, json.dumps(metadata or {}))
            return str(row['id'])
    
    async def create_rule(
        self,
        name: str,
        description: str,
        link_to_critical: bool = False
    ) -> str:
        """Create a new rule and optionally link to CriticalRules."""
        entity_id = await self.create_entity(name, "Rule", description)
        
        if link_to_critical:
            await self.link_to_critical_rules(entity_id)
        
        logger.info(f"Created rule '{name}' with ID: {entity_id}")
        return entity_id
    
    async def create_instruction(
        self,
        name: str,
        description: str,
        rule_ids: Optional[List[str]] = None
    ) -> str:
        """Create a new instruction and optionally link to rules."""
        entity_id = await self.create_entity(name, "Instruction", description)
        
        if rule_ids:
            for rule_id in rule_ids:
                await self.create_link(entity_id, rule_id, "uses")
        
        logger.info(f"Created instruction '{name}' with ID: {entity_id}")
        return entity_id
    
    async def create_protocol(
        self,
        name: str,
        description: str,
        instruction_ids: Optional[List[str]] = None,
        trigger_examples: Optional[List[str]] = None
    ) -> str:
        """Create a new protocol with instructions and triggers."""
        entity_id = await self.create_entity(name, "Protocol", description)
        
        if instruction_ids:
            for instruction_id in instruction_ids:
                await self.create_link(entity_id, instruction_id, "contains")
        
        if trigger_examples:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO protocol_triggers (protocol_id, trigger_examples, context_description)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (protocol_id) DO UPDATE
                    SET trigger_examples = EXCLUDED.trigger_examples,
                        context_description = EXCLUDED.context_description
                """, entity_id, trigger_examples, f"Triggers for {name} protocol")
        
        logger.info(f"Created protocol '{name}' with ID: {entity_id}")
        return entity_id
    
    async def link_to_critical_rules(self, entity_id: str):
        """Link an entity to CriticalRules system node."""
        async with self.pool.acquire() as conn:
            critical_rules_id = await conn.fetchval("""
                SELECT id FROM entity_nodes
                WHERE name = 'CriticalRules' AND type = 'SystemNode' AND valid_to IS NULL
                LIMIT 1
            """)
            
            if not critical_rules_id:
                logger.warning("CriticalRules node not found, skipping link")
                return
            
            await self.create_link(str(critical_rules_id), entity_id, "contains")
    
    async def create_link(
        self,
        source_id: str,
        target_id: str,
        relation_type: str
    ):
        """Create a link between two entities."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO entity_edges (source_id, target_id, relation_type)
                VALUES ($1, $2, $3)
                ON CONFLICT (source_id, target_id, relation_type) DO NOTHING
            """, source_id, target_id, relation_type)
    
    async def list_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """List entities, optionally filtered by type."""
        async with self.pool.acquire() as conn:
            if entity_type:
                rows = await conn.fetch("""
                    SELECT id, name, type, description, created_at
                    FROM entity_nodes
                    WHERE type = $1 AND valid_to IS NULL
                    ORDER BY created_at DESC
                    LIMIT $2
                """, entity_type, limit)
            else:
                rows = await conn.fetch("""
                    SELECT id, name, type, description, created_at
                    FROM entity_nodes
                    WHERE valid_to IS NULL
                    ORDER BY type, created_at DESC
                    LIMIT $2
                """, limit)
            
            return [dict(row) for row in rows]
    
    async def show_entity(self, entity_id: str) -> Optional[Dict]:
        """Show details of an entity."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, name, type, description, created_at, valid_from, valid_to
                FROM entity_nodes
                WHERE id = $1
            """, entity_id)
            
            if not row:
                return None
            
            entity = dict(row)
            
            # Get links
            outgoing = await conn.fetch("""
                SELECT e.target_id, e.relation_type, n.name, n.type
                FROM entity_edges e
                JOIN entity_nodes n ON e.target_id = n.id
                WHERE e.source_id = $1 AND e.valid_to IS NULL
            """, entity_id)
            
            incoming = await conn.fetch("""
                SELECT e.source_id, e.relation_type, n.name, n.type
                FROM entity_edges e
                JOIN entity_nodes n ON e.source_id = n.id
                WHERE e.target_id = $1 AND e.valid_to IS NULL
            """, entity_id)
            
            entity['outgoing_links'] = [dict(r) for r in outgoing]
            entity['incoming_links'] = [dict(r) for r in incoming]
            
            return entity
    
    async def search_entities(
        self,
        query: str,
        entity_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """Search entities by name or description."""
        async with self.pool.acquire() as conn:
            if entity_type:
                rows = await conn.fetch("""
                    SELECT id, name, type, description, created_at
                    FROM entity_nodes
                    WHERE (name ILIKE $1 OR description ILIKE $1)
                    AND type = $2
                    AND valid_to IS NULL
                    ORDER BY created_at DESC
                    LIMIT $3
                """, f"%{query}%", entity_type, limit)
            else:
                rows = await conn.fetch("""
                    SELECT id, name, type, description, created_at
                    FROM entity_nodes
                    WHERE (name ILIKE $1 OR description ILIKE $1)
                    AND valid_to IS NULL
                    ORDER BY created_at DESC
                    LIMIT $2
                """, f"%{query}%", limit)
            
            return [dict(row) for row in rows]


def print_entity_list(entities: List[Dict]):
    """Print list of entities."""
    if not entities:
        print("No entities found")
        return
    
    print(f"\nFound {len(entities)} entity(ies):\n")
    for entity in entities:
        print(f"  [{entity['type']}] {entity['name']}")
        print(f"    ID: {entity['id']}")
        if entity['description']:
            desc = entity['description'][:100]
            if len(entity['description']) > 100:
                desc += "..."
            print(f"    Description: {desc}")
        print()


def print_entity_details(entity: Dict):
    """Print detailed entity information."""
    print(f"\nEntity: {entity['name']}")
    print(f"  Type: {entity['type']}")
    print(f"  ID: {entity['id']}")
    print(f"  Created: {entity['created_at']}")
    if entity['description']:
        print(f"  Description: {entity['description']}")
    
    if entity.get('outgoing_links'):
        print(f"\n  Outgoing links ({len(entity['outgoing_links'])}):")
        for link in entity['outgoing_links']:
            print(f"    - {link['relation_type']} → [{link['type']}] {link['name']}")
    
    if entity.get('incoming_links'):
        print(f"\n  Incoming links ({len(entity['incoming_links'])}):")
        for link in entity['incoming_links']:
            print(f"    ← {link['relation_type']} [{link['type']}] {link['name']}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Knowledge Graph CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--connection-string",
        help="Database connection string (overrides NEON_CONNECTION_STRING)"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Create rule
    create_rule_parser = subparsers.add_parser("create-rule", help="Create a new rule")
    create_rule_parser.add_argument("--name", required=True, help="Rule name")
    create_rule_parser.add_argument("--description", required=True, help="Rule description")
    create_rule_parser.add_argument(
        "--link-to-critical",
        action="store_true",
        help="Link to CriticalRules system node"
    )
    
    # Create instruction
    create_inst_parser = subparsers.add_parser("create-instruction", help="Create a new instruction")
    create_inst_parser.add_argument("--name", required=True, help="Instruction name")
    create_inst_parser.add_argument("--description", required=True, help="Instruction description")
    create_inst_parser.add_argument(
        "--rule-ids",
        nargs="+",
        help="Rule IDs to link (uses relation)"
    )
    
    # Create protocol
    create_proto_parser = subparsers.add_parser("create-protocol", help="Create a new protocol")
    create_proto_parser.add_argument("--name", required=True, help="Protocol name")
    create_proto_parser.add_argument("--description", required=True, help="Protocol description")
    create_proto_parser.add_argument(
        "--instruction-ids",
        nargs="+",
        help="Instruction IDs to link (contains relation)"
    )
    create_proto_parser.add_argument(
        "--triggers",
        nargs="+",
        help="Trigger example phrases"
    )
    
    # List entities
    list_parser = subparsers.add_parser("list", help="List entities")
    list_parser.add_argument("--type", help="Filter by entity type")
    list_parser.add_argument("--limit", type=int, default=50, help="Limit results")
    
    # Show entity
    show_parser = subparsers.add_parser("show", help="Show entity details")
    show_parser.add_argument("--id", required=True, help="Entity ID")
    
    # Search
    search_parser = subparsers.add_parser("search", help="Search entities")
    search_parser.add_argument("--query", required=True, help="Search query")
    search_parser.add_argument("--type", help="Filter by entity type")
    search_parser.add_argument("--limit", type=int, default=20, help="Limit results")
    
    # Link entities
    link_parser = subparsers.add_parser("link", help="Link two entities")
    link_parser.add_argument("--source-id", required=True, help="Source entity ID")
    link_parser.add_argument("--target-id", required=True, help="Target entity ID")
    link_parser.add_argument("--relation-type", required=True, help="Relation type")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Get connection string
    connection_string = args.connection_string or os.getenv("NEON_CONNECTION_STRING")
    if not connection_string:
        logger.error(
            "Connection string required. "
            "Set NEON_CONNECTION_STRING env var or use --connection-string"
        )
        return 1
    
    # Initialize CLI
    cli = KnowledgeGraphCLI(connection_string)
    await cli.connect()
    
    try:
        if args.command == "create-rule":
            await cli.create_rule(
                args.name,
                args.description,
                args.link_to_critical
            )
        
        elif args.command == "create-instruction":
            await cli.create_instruction(
                args.name,
                args.description,
                args.rule_ids
            )
        
        elif args.command == "create-protocol":
            await cli.create_protocol(
                args.name,
                args.description,
                args.instruction_ids,
                args.triggers
            )
        
        elif args.command == "list":
            entities = await cli.list_entities(args.type, args.limit)
            print_entity_list(entities)
        
        elif args.command == "show":
            entity = await cli.show_entity(args.id)
            if entity:
                print_entity_details(entity)
            else:
                print(f"Entity with ID {args.id} not found")
                return 1
        
        elif args.command == "search":
            entities = await cli.search_entities(args.query, args.type, args.limit)
            print_entity_list(entities)
        
        elif args.command == "link":
            await cli.create_link(args.source_id, args.target_id, args.relation_type)
            logger.info(f"Linked {args.source_id} --[{args.relation_type}]--> {args.target_id}")
        
        return 0
        
    finally:
        await cli.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
