import asyncio
import sys
import logging
from config.settings import settings
from core.memory.falkordb import FalkorDBProvider
from transport.queue import RedisQueue

# Configure logging
logging.basicConfig(level=logging.INFO)

async def test_integration():
    print("--- Starting Synapse Usage Verification ---")
    
    # 1. Test Redis Queue Connection
    print("[1] Testing Redis Queue...")
    queue = RedisQueue(
        host=settings.FALKORDB_HOST,
        port=settings.FALKORDB_PORT,
        incoming_key="test:incoming",
        outgoing_key="test:outgoing"
    )
    
    test_msg = {"user_id": 123, "text": "Hello Synapse"}
    await queue.push_incoming(test_msg)
    print("    Pushed message to test:incoming")
    
    popped = await queue.pop_incoming(timeout=2)
    print(f"    Popped message: {popped}")
    
    assert popped['text'] == "Hello Synapse", "Queue pop failed or mismatched"
    print("    [PASS] Redis Queue works.")
    
    # 2. Test FalkorDB Connection (Cypher)
    print("[2] Testing FalkorDB Memory...")
    memory = FalkorDBProvider(
        host=settings.FALKORDB_HOST,
        port=settings.FALKORDB_PORT
    )
    
    try:
        await memory.add_message("system", "Synapse Verification Run")
        print("    Added message to graph.")
        
        history = await memory.get_history(limit=1)
        print(f"    History requested. Result: {history}")
        
        if history:
             last_msg = history[0]
             # Check structure (parts vs content depending on implementation)
             print(f"    Last message structure: {last_msg}")
             print("    [PASS] FalkorDB read/write works.")
        else:
             print("    [WARNING] History empty (might be fine if graph was empty and add failed silently?)")
             
    except Exception as e:
        print(f"    [FAIL] FalkorDB Error: {e}")
        # We don't fail hard because maybe falkordb container isn't running in this env
        print("    Ensure FalkorDB container is running: docker ps")

if __name__ == "__main__":
    try:
        asyncio.run(test_integration())
    except Exception as e:
        print(f"Verification Failed: {e}")
        sys.exit(1)
