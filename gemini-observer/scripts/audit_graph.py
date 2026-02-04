#!/usr/bin/env python3
"""
Graph Audit Script for GeminiMemory.

Checks graph integrity by verifying all relationships exist.

Usage:
    python scripts/audit_graph.py
"""

import asyncio
import os
import redis.asyncio as redis

# Configuration  
REDIS_HOST = os.environ.get("REDIS_HOST", "falkordb")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
GRAPH_NAME = "GeminiMemory"


async def get_redis_client():
    """Create async Redis connection."""
    return await redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)


async def query(client: redis.Redis, cypher: str) -> list:
    """Execute Cypher query and return results."""
    result = await client.execute_command("GRAPH.QUERY", GRAPH_NAME, cypher)
    return result


def get_count(result) -> int:
    """Extract count from query result."""
    if result and len(result) > 1 and result[1]:
        val = result[1][0][0]
        return int(val) if val else 0
    return 0


async def main():
    """Run graph audit."""
    print("=" * 60)
    print("🔍 Graph Audit for GeminiMemory")
    print("=" * 60 + "\n")
    
    client = await get_redis_client()
    
    try:
        # Total counts
        total_messages = get_count(await query(client, "MATCH (m:Message) RETURN count(m)"))
        total_users = get_count(await query(client, "MATCH (u:User) RETURN count(u)"))
        total_agents = get_count(await query(client, "MATCH (a:Agent) RETURN count(a)"))
        total_days = get_count(await query(client, "MATCH (d:Day) RETURN count(d)"))
        total_chats = get_count(await query(client, "MATCH (c:Chat) RETURN count(c)"))
        
        print("📊 Node Counts:")
        print(f"   Messages: {total_messages}")
        print(f"   Users: {total_users}")
        print(f"   Agents: {total_agents}")
        print(f"   Days: {total_days}")
        print(f"   Chats: {total_chats}")
        print()
        
        # Relationship counts
        authored = get_count(await query(client, "MATCH ()-[r:AUTHORED]->() RETURN count(r)"))
        generated = get_count(await query(client, "MATCH ()-[r:GENERATED]->() RETURN count(r)"))
        happened_in = get_count(await query(client, "MATCH ()-[r:HAPPENED_IN]->() RETURN count(r)"))
        happened_at = get_count(await query(client, "MATCH ()-[r:HAPPENED_AT]->() RETURN count(r)"))
        next_rels = get_count(await query(client, "MATCH ()-[r:NEXT]->() RETURN count(r)"))
        last_event = get_count(await query(client, "MATCH ()-[r:LAST_EVENT]->() RETURN count(r)"))
        
        print("🔗 Relationship Counts:")
        print(f"   AUTHORED: {authored}")
        print(f"   GENERATED: {generated}")
        print(f"   HAPPENED_IN: {happened_in}")
        print(f"   HAPPENED_AT: {happened_at}")
        print(f"   NEXT: {next_rels}")
        print(f"   LAST_EVENT: {last_event}")
        print()
        
        # Integrity checks
        print("✅ Integrity Checks:")
        
        # 1. Orphan messages (no author)
        orphan = get_count(await query(client, 
            "MATCH (m:Message) WHERE NOT (()-[:AUTHORED]->(m) OR ()-[:GENERATED]->(m)) RETURN count(m)"))
        status = "✅" if orphan == 0 else "❌"
        print(f"   {status} Messages without author: {orphan}")
        
        # 2. Messages without chat
        no_chat = get_count(await query(client,
            "MATCH (m:Message) WHERE NOT (m)-[:HAPPENED_IN]->(:Chat) RETURN count(m)"))
        status = "✅" if no_chat == 0 else "❌"
        print(f"   {status} Messages without chat: {no_chat}")
        
        # 3. Messages without day
        no_day = get_count(await query(client,
            "MATCH (m:Message) WHERE NOT (m)-[:HAPPENED_AT]->(:Day) RETURN count(m)"))
        status = "✅" if no_day == 0 else "❌"
        print(f"   {status} Messages without day: {no_day}")
        
        # 4. Chain integrity (NEXT links)
        expected_next = total_messages - total_chats  # Each chat should have one "head" without NEXT
        status = "✅" if next_rels >= expected_next - total_chats else "⚠️"
        print(f"   {status} NEXT chain links: {next_rels} (expected ~{total_messages - total_chats})")
        
        # 5. LAST_EVENT per chat
        status = "✅" if last_event == total_chats else "⚠️"
        print(f"   {status} LAST_EVENT pointers: {last_event} (expected {total_chats})")
        
        # Summary
        print()
        all_ok = orphan == 0 and no_chat == 0 and no_day == 0
        if all_ok:
            print("🎉 All integrity checks PASSED!")
        else:
            print("⚠️ Some integrity issues found. Review above.")
        
        print("=" * 60)
        
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
