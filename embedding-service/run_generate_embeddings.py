#!/usr/bin/env python3
"""Quick script to generate embeddings"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import db
from app.embedding import EmbeddingService
from app.config import settings

async def main():
    if not settings.neon_connection_string:
        print("ERROR: NEON_CONNECTION_STRING not set!")
        return
    
    await db.connect()
    if not db.pool:
        print("ERROR: Database not connected!")
        return
    
    embedding_service = EmbeddingService()
    
    if not await embedding_service.health_check():
        print("ERROR: Ollama not available!")
        await db.disconnect()
        return
    
    messages = await db.get_messages_without_embeddings()
    print(f"Found {len(messages)} messages without embeddings")
    
    success = 0
    errors = 0
    
    for i, msg in enumerate(messages, 1):
        print(f"[{i}/{len(messages)}] Processing...", end=" ")
        try:
            embedding = await embedding_service.generate_embedding(msg['content'])
            updated = await db.update_message_embedding(msg['id'], embedding)
            if updated:
                success += 1
                print("✓")
            else:
                errors += 1
                print("✗")
        except Exception as e:
            errors += 1
            print(f"✗ ({str(e)[:30]})")
    
    print(f"\nDone! Success: {success}, Errors: {errors}")
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

