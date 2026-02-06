import asyncio
import redis.asyncio as redis
import json
import logging
import sys
import os
from datetime import datetime
import uuid

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def verify_scribe():
    logger.info("🧪 Starting Scribe Verification...")
    
    redis_url = f"redis://{settings.FALKORDB_HOST}:{settings.FALKORDB_PORT}"
    client = redis.from_url(redis_url, encoding="utf-8", decode_responses=False)
    
    # 1. Clear Queues
    await client.delete(settings.REDIS_QUEUE_INCOMING)
    await client.delete(settings.REDIS_QUEUE_BRAIN)
    logger.info("🧹 Queues cleared.")

    # 1.5 Start Scribe Instance (Background)
    from streams.scribe import Scribe
    from transport.queue import RedisQueue
    from memory.falkordb import FalkorDBProvider
    
    queue_ingress = RedisQueue(client, settings.REDIS_QUEUE_INCOMING, settings.REDIS_QUEUE_OUTGOING)
    memory = FalkorDBProvider(client)
    scribe = Scribe(queue_ingress, memory)
    
    scribe_task = asyncio.create_task(scribe.start())
    logger.info("📜 Scribe instance started for testing...")
    
    # 2. Inject Test Events
    TEST_COUNT = 10
    logger.info(f"📤 Injecting {TEST_COUNT} test events to {settings.REDIS_QUEUE_INCOMING}...")
    
    chat_id = -100999
    user_id = 12345
    
    logger.info("🔥 Injecting WARMUP event...")
    warmup_event = {
        "chat_id": chat_id, "user_id": user_id, "text": "Warmup", 
        "timestamp": datetime.now().isoformat(), "message_id": 8999
    }
    await client.rpush(settings.REDIS_QUEUE_INCOMING, json.dumps(warmup_event))
    await asyncio.sleep(1)
    
    events = []
    for i in range(TEST_COUNT):
        event = {
            "chat_id": chat_id,
            "user_id": user_id,
            "text": f"Verification Message {i}",
            "timestamp": datetime.now().isoformat(),
            "message_id": 9000 + i,
            "author_name": "Test User"
        }
        await client.rpush(settings.REDIS_QUEUE_INCOMING, json.dumps(event))
        events.append(event)
        
    logger.info("⏳ Waiting for Scribe to process (5 seconds)...")
    await asyncio.sleep(5)
    
    # Stop Scribe
    await scribe.stop()
    try:
        await scribe_task
    except:
        pass
    
    # 3. Verify Brain Queue
    brain_length = await client.llen(settings.REDIS_QUEUE_BRAIN)
    logger.info(f"🧠 Brain Queue Length: {brain_length} (Expected: {TEST_COUNT})")

    
    if brain_length != TEST_COUNT:
        logger.error("❌ Brain Queue count mismatch! Scribe might not be forwarding.")
    else:
        logger.info("✅ Scribe Forwarding Logic: OK")
        
    # 4. Verify FalkorDB
    logger.info("🔍 Checking FalkorDB for Graph persistence...")
    graph_name = settings.FALKORDB_GRAPH_GROUP # Or AGENT? FalkorDBProvider uses "GeminiMemory" by default?
    # Wait, FalkorDBProvider default is "GeminiMemory".
    # Settings has FALKORDB_GRAPH_AGENT="agent_memory", FALKORDB_GRAPH_GROUP="group_chat_memory"
    # Scribe uses memory_provider default?
    # In main.py: memory_provider = FalkorDBProvider(redis_client=redis_client)
    # FalkorDBProvider default graph_name="GeminiMemory".
    # So we check "GeminiMemory".
    
    graph_name = "GeminiMemory"
    
    query = f"MATCH (m:Message) WHERE m.message_id >= 9000 RETURN count(m)"
    try:
        result = await client.execute_command("GRAPH.QUERY", graph_name, query)
        # result[1][0][0] is count
        count = result[1][0][0]
        if isinstance(count, bytes):
            count = int(float(count.decode('utf-8')))
        else:
            count = int(count)
            
        logger.info(f"📊 FalkorDB Message Count: {count} (Expected: {TEST_COUNT})")
        
        if count == TEST_COUNT:
             logger.info("✅ Scribe Persistence Logic: OK")
        else:
             logger.warning(f"⚠️  Persistence mismatch. ({count}/{TEST_COUNT})")
             
    except Exception as e:
        logger.error(f"❌ FalkorDB Query Failed: {e}")

    await client.close()

if __name__ == "__main__":
    asyncio.run(verify_scribe())
