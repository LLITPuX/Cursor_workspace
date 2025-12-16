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
            "content": "Проанализируй последние сессии сделай комиты дла новых файло в и пуш. И сразусохрани эту сессию в базе"
        },
        {
            "role": "assistant",
            "content": """Проаналізував останні сесії та виконав наступне:

1. **Аналіз git статусу:**
   - Виявлено нові файли: .dockerignore, Dockerfile, Makefile, SAVE_SESSION.md, docker-compose файли, scripts/
   - Виявлено змінені файли: README.md, app/api/routes.py, app/config.py, app/database.py, app/embedding.py, app/main.py

2. **Виконано коміт:**
   - Додано всі нові файли та зміни
   - Створено коміт з описом: "feat: add Docker support, scripts, and improve embedding service"
   - Коміт включає: Docker конфігурації, Makefile, скрипти для збереження сесій, документацію

3. **Виконано push:**
   - Зміни успішно відправлено в репозиторій
   - Коміт ID: 4ca3046

4. **Збереження сесії:**
   - Створюю сесію в базі даних з поточними повідомленнями
   - Генерую embeddings для всіх повідомлень"""
        }
    ]
    
    try:
        # Create session
        session_id = await db.create_session(
            topic="Аналіз сесій, коміти та збереження в базі",
            metadata={
                "test": False,
                "source": "current_session_script",
                "description": "Сесія аналізу останніх змін, створення комітів та збереження в базі даних",
                "commit_id": "4ca3046",
                "files_added": [
                    ".dockerignore", "Dockerfile", "Makefile", "SAVE_SESSION.md",
                    "docker-compose.dev.yml", "docker-compose.yml",
                    "scripts/init-ollama.sh", "scripts/save_current_session.py", "scripts/save_test_session.py"
                ],
                "files_modified": [
                    "README.md", "app/api/routes.py", "app/config.py",
                    "app/database.py", "app/embedding.py", "app/main.py"
                ]
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

