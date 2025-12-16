#!/usr/bin/env python3
"""Script to save current session (our conversation) to the database"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import db
from app.embedding import EmbeddingService
from app.config import settings


async def save_current_session():
    """Save current session with our conversation"""
    
    # Check database connection
    if not settings.neon_connection_string:
        print("ERROR: NEON_CONNECTION_STRING not set!")
        print("Please set the environment variable or add it to .env file")
        print("\nExample:")
        print("  export NEON_CONNECTION_STRING='postgresql://user:pass@host/db?sslmode=require'")
        return False
    
    # Connect to database
    try:
        await db.connect()
        if not db.pool:
            print("ERROR: Database connection pool not initialized!")
            return False
        print("✓ Connected to database")
    except Exception as e:
        print(f"ERROR: Failed to connect to database: {e}")
        print("\nPlease check your NEON_CONNECTION_STRING")
        return False
    
    # Initialize embedding service
    embedding_service = EmbeddingService()
    
    # Our conversation messages
    messages = [
        {
            "role": "user",
            "content": "Собери контейнер и протестируй эмбендинг-сервис"
        },
        {
            "role": "assistant",
            "content": """Контейнер зібрано та запущено. Ollama працює (модель embeddinggemma:latest завантажена). Embedding-сервіс працює.

Протестовані endpoints:
- Health Check (/api/v1/health) - працює
- Генерація embedding (/api/v1/embed) - працює, розмірність 768
- Список стратегій (/api/v1/strategies) - працює
- Chunked Embedding (/api/v1/embed-chunked) - працює

Виправлено batch-обробку embeddings (послідовні виклики замість batch API)."""
        },
        {
            "role": "user",
            "content": "Сохрани сессию в базу"
        },
        {
            "role": "assistant",
            "content": """Додано функціональність збереження сесій у базу даних:

1. Методи в database.py:
   - create_session() - створює нову сесію
   - save_message() - зберігає повідомлення з embedding

2. API endpoint:
   - POST /api/v1/sessions - зберігає сесію з повідомленнями та embeddings

3. Скрипт для тестування:
   - scripts/save_test_session.py - зберігає тестову сесію

4. Документація:
   - SAVE_SESSION.md - інструкція з використання

Особливості:
- Автоматична генерація embeddings для всіх повідомлень
- Збереження навіть якщо генерація embedding не вдалася
- Використання embedding_v2 (768d) для EmbeddingGemma"""
        }
    ]
    
    try:
        # Create session
        session_id = await db.create_session(
            topic="Збірка та тестування embedding-сервісу",
            metadata={
                "test": False,
                "source": "current_session_script",
                "description": "Сесія збірки та тестування embedding-сервісу"
            }
        )
        print(f"✓ Created session: {session_id}")
        
        # Save messages with embeddings
        embeddings_generated = 0
        for i, msg in enumerate(messages, 1):
            print(f"  Processing message {i}/{len(messages)} ({msg['role']})...", end=" ")
            
            # Generate embedding
            try:
                embedding = await embedding_service.generate_embedding(msg["content"])
                embeddings_generated += 1
                print("✓ (embedding generated)")
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
        print(f"  Embeddings generated: {embeddings_generated}/{len(messages)}")
        print(f"\nYou can query the session with:")
        print(f"  SELECT * FROM messages WHERE session_id = '{session_id}' ORDER BY created_at;")
        
        return True
        
    except Exception as e:
        print(f"\nERROR: Failed to save session: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await db.disconnect()
        print("✓ Disconnected from database")


if __name__ == "__main__":
    success = asyncio.run(save_current_session())
    sys.exit(0 if success else 1)

