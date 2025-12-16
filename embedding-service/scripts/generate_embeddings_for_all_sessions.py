#!/usr/bin/env python3
"""Script to generate embeddings for all sessions without embeddings"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import db
from app.embedding import EmbeddingService
from app.config import settings
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def generate_embeddings_for_all_sessions():
    """Generate embeddings for all messages without embeddings"""
    
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
        return False
    
    # Initialize embedding service
    embedding_service = EmbeddingService()
    
    # Check Ollama availability
    print("Checking Ollama service...", end=" ")
    if not await embedding_service.health_check():
        print("✗")
        print("ERROR: Ollama service is not available!")
        print(f"Please ensure Ollama is running at {settings.ollama_base_url}")
        return False
    print("✓")
    
    try:
        # Get all messages without embeddings
        print("\nFetching messages without embeddings...", end=" ")
        messages = await db.get_messages_without_embeddings()
        print(f"✓ Found {len(messages)} messages")
        
        if not messages:
            print("\n✓ All messages already have embeddings!")
            return True
        
        # Group by session for better reporting
        sessions = {}
        for msg in messages:
            session_id = msg['session_id'] or 'no_session'
            if session_id not in sessions:
                sessions[session_id] = []
            sessions[session_id].append(msg)
        
        print(f"  Sessions to process: {len(sessions)}")
        print(f"  Total messages to process: {len(messages)}\n")
        
        # Process messages
        success_count = 0
        error_count = 0
        
        for i, msg in enumerate(messages, 1):
            session_id = msg['session_id'] or 'no_session'
            print(f"[{i}/{len(messages)}] Session: {session_id[:8]}... | Role: {msg['role']:8} | ", end="")
            
            # Generate embedding
            try:
                embedding = await embedding_service.generate_embedding(msg['content'])
                
                # Update message with embedding
                updated = await db.update_message_embedding(msg['id'], embedding)
                
                if updated:
                    success_count += 1
                    print("✓")
                else:
                    error_count += 1
                    print(f"✗ (update failed)")
                    
            except Exception as e:
                error_count += 1
                print(f"✗ (error: {str(e)[:50]})")
                logger.error(f"Failed to generate embedding for message {msg['id']}: {e}")
        
        # Print summary
        print("\n" + "="*60)
        print("SUMMARY:")
        print(f"  Total messages processed: {len(messages)}")
        print(f"  Successfully updated: {success_count}")
        print(f"  Errors: {error_count}")
        print(f"  Success rate: {success_count/len(messages)*100:.1f}%")
        print("="*60)
        
        return error_count == 0
        
    except Exception as e:
        print(f"\nERROR: Failed to process messages: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await db.disconnect()
        print("\n✓ Disconnected from database")


if __name__ == "__main__":
    success = asyncio.run(generate_embeddings_for_all_sessions())
    sys.exit(0 if success else 1)

