#!/usr/bin/env python3
"""
Універсальний скрипт для збереження сесії в базу даних.

Може приймати дані з:
- stdin (JSON)
- файлу (--file)
- аргументів командного рядка (--topic, --messages)
- або використовувати API endpoint (--use-api)

Приклади використання:

1. З stdin:
   echo '{"topic": "Test", "messages": [{"role": "user", "content": "Hello"}]}' | python save_session.py

2. З файлу:
   python save_session.py --file session.json

3. З аргументів:
   python save_session.py --topic "Test" --messages '[{"role": "user", "content": "Hello"}]'

4. Через API (якщо сервер запущений):
   python save_session.py --use-api --file session.json
"""
import asyncio
import sys
import os
import json
import argparse
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import db
from app.embedding import EmbeddingService
from app.config import settings


async def save_session_via_api(data: Dict) -> bool:
    """Save session via API endpoint"""
    import httpx
    
    api_url = os.getenv("API_URL", "http://localhost:8000")
    endpoint = f"{api_url}/api/v1/sessions"
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, json=data)
            response.raise_for_status()
            result = response.json()
            
            print(f"✓ Session saved via API!")
            print(f"  Session ID: {result['session_id']}")
            print(f"  Messages saved: {result['messages_saved']}")
            print(f"  Embeddings generated: {result['embeddings_generated']}")
            return True
    except httpx.HTTPError as e:
        print(f"✗ API request failed: {e}")
        return False


async def save_session_direct(data: Dict) -> bool:
    """Save session directly to database"""
    
    # Check database connection
    if not settings.neon_connection_string:
        print("ERROR: NEON_CONNECTION_STRING not set!")
        print("Please set the environment variable or add it to .env file")
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
    
    # Check Ollama availability if generating embeddings
    if data.get("generate_embeddings", True):
        print("Checking Ollama service...", end=" ")
        if not await embedding_service.health_check():
            print("✗")
            print("ERROR: Ollama service is not available!")
            return False
        print("✓")
    
    try:
        # Create session
        session_id = await db.create_session(
            topic=data.get("topic"),
            metadata=data.get("metadata", {"source": "save_session_script"})
        )
        print(f"✓ Created session: {session_id}")
        
        # Save messages with embeddings
        messages = data.get("messages", [])
        generate_embeddings = data.get("generate_embeddings", True)
        embeddings_generated = 0
        
        for i, msg in enumerate(messages, 1):
            print(f"  Processing message {i}/{len(messages)} ({msg.get('role', 'unknown')})...", end=" ")
            
            embedding = None
            if generate_embeddings:
                try:
                    embedding = await embedding_service.generate_embedding(msg["content"])
                    embeddings_generated += 1
                    print("✓ (embedding generated)")
                except Exception as e:
                    print(f"✗ (embedding failed: {e})")
                    embedding = None
            else:
                print("✓ (no embedding)")
            
            # Save message
            await db.save_message(
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


def load_data_from_stdin() -> Optional[Dict]:
    """Load JSON data from stdin"""
    try:
        data = sys.stdin.read()
        if not data.strip():
            return None
        return json.loads(data)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in stdin: {e}")
        return None


def load_data_from_file(filepath: str) -> Optional[Dict]:
    """Load JSON data from file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: File not found: {filepath}")
        return None
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in file: {e}")
        return None


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Save session to database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # From stdin
  echo '{"topic": "Test", "messages": [{"role": "user", "content": "Hello"}]}' | python save_session.py
  
  # From file
  python save_session.py --file session.json
  
  # Using API
  python save_session.py --use-api --file session.json
  
  # With command line arguments
  python save_session.py --topic "Test" --messages '[{"role": "user", "content": "Hello"}]'
        """
    )
    
    parser.add_argument(
        "--file", "-f",
        help="Path to JSON file with session data"
    )
    
    parser.add_argument(
        "--use-api",
        action="store_true",
        help="Use API endpoint instead of direct database access"
    )
    
    parser.add_argument(
        "--topic", "-t",
        help="Session topic"
    )
    
    parser.add_argument(
        "--messages", "-m",
        help="JSON array of messages"
    )
    
    parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Don't generate embeddings"
    )
    
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)"
    )
    
    return parser.parse_args()


async def main():
    """Main function"""
    args = parse_args()
    
    # Load data from various sources
    data = None
    
    if args.file:
        data = load_data_from_file(args.file)
    elif args.topic or args.messages:
        # Build data from command line arguments
        data = {}
        if args.topic:
            data["topic"] = args.topic
        if args.messages:
            try:
                data["messages"] = json.loads(args.messages)
            except json.JSONDecodeError as e:
                print(f"ERROR: Invalid JSON in --messages: {e}")
                return 1
        else:
            print("ERROR: --messages is required when using --topic")
            return 1
    else:
        # Try to read from stdin
        data = load_data_from_stdin()
    
    if not data:
        print("ERROR: No data provided!")
        print("Use --file, --topic/--messages, or provide JSON via stdin")
        return 1
    
    # Validate data structure
    if "messages" not in data:
        print("ERROR: 'messages' field is required in data")
        return 1
    
    if not isinstance(data["messages"], list) or len(data["messages"]) == 0:
        print("ERROR: 'messages' must be a non-empty array")
        return 1
    
    # Set generate_embeddings flag
    if args.no_embeddings:
        data["generate_embeddings"] = False
    elif "generate_embeddings" not in data:
        data["generate_embeddings"] = True
    
    # Set API URL if using API
    if args.use_api:
        os.environ["API_URL"] = args.api_url
        success = await save_session_via_api(data)
    else:
        success = await save_session_direct(data)
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


