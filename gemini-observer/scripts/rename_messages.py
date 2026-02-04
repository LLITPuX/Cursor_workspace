#!/usr/bin/env python3
"""
Message Renaming Script for GeminiMemory Graph.

Assigns sequential names to messages based on author and day.
Format: {ABBREV}{SEQ:02d} (e.g., MA01, BS02, YU03)

Mapping:
- telegram_id -> 2-letter abbreviation
- Sequence number = order of message from that author on that day

Usage:
    python scripts/rename_messages.py
    python scripts/rename_messages.py --dry-run
"""

import asyncio
import argparse
import redis.asyncio as redis
from datetime import datetime
from collections import defaultdict

# Configuration
import os
REDIS_HOST = os.environ.get("REDIS_HOST", "falkordb")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
GRAPH_NAME = "GeminiMemory"

# Static mapping for known authors
AUTHOR_ABBREV = {
    298085237: "MA",      # Maks
    5561942654: "YU",     # Yulianna
    8521381973: "BS",     # Bober Sikfan (Agent)
}


async def get_redis_client():
    """Create async Redis connection."""
    return await redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)


async def query(client: redis.Redis, cypher: str) -> list:
    """Execute Cypher query and return results."""
    result = await client.execute_command("GRAPH.QUERY", GRAPH_NAME, cypher)
    return result


def decode_value(val):
    """Decode bytes or return as-is."""
    if isinstance(val, bytes):
        return val.decode('utf-8')
    return val


async def get_all_days(client: redis.Redis) -> list:
    """Get all days from the graph."""
    result = await query(client, "MATCH (d:Day) RETURN d.date ORDER BY d.date")
    if not result or len(result) < 2:
        return []
    return [decode_value(row[0]) for row in result[1]]


async def get_messages_for_day(client: redis.Redis, day_date: str) -> list:
    """Get all messages for a specific day with author info."""
    cypher = f"""
    MATCH (d:Day {{date: '{day_date}'}})
    MATCH (m:Message)-[:HAPPENED_AT]->(d)
    MATCH (author)-[:AUTHORED|GENERATED]->(m)
    RETURN m.uid as uid, m.name as current_name, author.telegram_id as author_id, m.created_at as ts
    ORDER BY m.created_at
    """
    result = await query(client, cypher)
    
    if not result or len(result) < 2:
        return []
    
    messages = []
    for row in result[1]:
        uid = decode_value(row[0])
        current_name = decode_value(row[1])
        author_id = int(row[2]) if row[2] else 0
        ts = float(row[3]) if row[3] else 0.0
        messages.append({
            'uid': uid,
            'current_name': current_name,
            'author_id': author_id,
            'ts': ts
        })
    
    return messages


def compute_new_names(messages: list) -> dict:
    """
    Compute new names for messages based on author sequence per day.
    
    Returns: dict {uid: new_name}
    """
    # Count messages per author
    author_counters = defaultdict(int)
    uid_to_new_name = {}
    
    for msg in messages:
        author_id = msg['author_id']
        author_counters[author_id] += 1
        seq = author_counters[author_id]
        
        # Get abbreviation
        abbrev = AUTHOR_ABBREV.get(author_id, "XX")
        
        # Format: {ABBREV}{SEQ:02d}
        new_name = f"{abbrev}{seq:02d}"
        uid_to_new_name[msg['uid']] = new_name
    
    return uid_to_new_name


async def update_message_name(client: redis.Redis, uid: str, new_name: str) -> bool:
    """Update message name in the graph."""
    safe_uid = uid.replace("'", "\\'")
    cypher = f"MATCH (m:Message {{uid: '{safe_uid}'}}) SET m.name = '{new_name}' RETURN m.uid"
    try:
        await query(client, cypher)
        return True
    except Exception as e:
        print(f"  ❌ Error updating {uid}: {e}")
        return False


async def main(dry_run: bool = False):
    """Main execution."""
    print("=" * 60)
    print("🔧 Message Renaming Script for GeminiMemory")
    print("=" * 60)
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made\n")
    
    client = await get_redis_client()
    
    try:
        # Get all days
        days = await get_all_days(client)
        print(f"📅 Found {len(days)} days in graph: {days}\n")
        
        total_updated = 0
        total_skipped = 0
        
        for day_date in days:
            print(f"📆 Processing day: {day_date}")
            
            # Get messages for this day
            messages = await get_messages_for_day(client, day_date)
            print(f"   Found {len(messages)} messages")
            
            if not messages:
                continue
            
            # Compute new names
            new_names = compute_new_names(messages)
            
            # Apply updates
            for msg in messages:
                uid = msg['uid']
                old_name = msg['current_name']
                new_name = new_names.get(uid, old_name)
                
                if old_name == new_name:
                    total_skipped += 1
                    continue
                
                if dry_run:
                    print(f"   📝 Would rename: {uid} [{old_name}] → [{new_name}]")
                else:
                    success = await update_message_name(client, uid, new_name)
                    if success:
                        print(f"   ✅ Renamed: {uid} [{old_name}] → [{new_name}]")
                        total_updated += 1
                    else:
                        total_skipped += 1
            
            print()
        
        # Summary
        print("=" * 60)
        print("📊 Summary:")
        print(f"   Total messages processed: {total_updated + total_skipped}")
        print(f"   Updated: {total_updated}")
        print(f"   Skipped (already correct): {total_skipped}")
        print("=" * 60)
        
    finally:
        await client.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rename messages in GeminiMemory graph")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()
    
    asyncio.run(main(dry_run=args.dry_run))
