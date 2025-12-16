#!/usr/bin/env python3
"""Script to save a test session to the database"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import db
from app.embedding import EmbeddingService
from app.config import settings


async def save_test_session():
    """Save a test session with messages and embeddings"""
    
    # Check database connection
    if not settings.neon_connection_string:
        print("ERROR: NEON_CONNECTION_STRING not set!")
        print("Please set the environment variable or add it to .env file")
        return
    
    # Connect to database
    try:
        await db.connect()
        print("✓ Connected to database")
    except Exception as e:
        print(f"ERROR: Failed to connect to database: {e}")
        return
    
    # Initialize embedding service
    embedding_service = EmbeddingService()
    
    # Test messages
    messages = [
        {
            "role": "user",
            "content": "Привіт! Я хочу протестувати embedding-сервіс."
        },
        {
            "role": "assistant",
            "content": "Привіт! Я готовий допомогти з тестуванням embedding-сервісу. Сервіс використовує модель EmbeddingGemma з розмірністю 768."
        },
        {
            "role": "user",
            "content": "Як працює чанкінг тексту?"
        },
        {
            "role": "assistant",
            "content": "Чанкінг тексту розбиває великі тексти на менші частини. Сервіс підтримує три стратегії: simple (простий), recursive (на природних межах) та semantic (семантичний)."
        }
    ]
    
    try:
        # Create session
        session_id = await db.create_session(
            topic="Тестування embedding-сервісу",
            metadata={"test": True, "source": "test_script"}
        )
        print(f"✓ Created session: {session_id}")
        
        # Save messages with embeddings
        embeddings_generated = 0
        for i, msg in enumerate(messages, 1):
            print(f"  Processing message {i}/{len(messages)}...", end=" ")
            
            # Generate embedding
            try:
                embedding = await embedding_service.generate_embedding(msg["content"])
                embeddings_generated += 1
                print("✓ (with embedding)")
            except Exception as e:
                print(f"✗ (embedding failed: {e})")
                embedding = None
            
            # Save message
            message_id = await db.save_message(
                session_id=session_id,
                role=msg["role"],
                content=msg["content"],
                embedding=embedding
            )
        
        print(f"\n✓ Session saved successfully!")
        print(f"  Session ID: {session_id}")
        print(f"  Messages saved: {len(messages)}")
        print(f"  Embeddings generated: {embeddings_generated}")
        
    except Exception as e:
        print(f"\nERROR: Failed to save session: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.disconnect()
        print("✓ Disconnected from database")


if __name__ == "__main__":
    asyncio.run(save_test_session())

