import asyncio
import redis.asyncio as redis
import logging
import sys
import os

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from core.memory.schema import GraphSchema

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def apply_schema():
    logger.info(f"Connecting to FalkorDB at {settings.FALKORDB_HOST}:{settings.FALKORDB_PORT}...")
    
    redis_url = f"redis://{settings.FALKORDB_HOST}:{settings.FALKORDB_PORT}"
    redis_client = redis.from_url(redis_url, encoding="utf-8", decode_responses=False)
    
    graph_name = GraphSchema.GRAPH_NAME
    constraints = GraphSchema.get_constraints()
    
    logger.info(f" applying {len(constraints)} constraints to graph '{graph_name}'...")
    
    for label, prop in constraints:
        try:
            # Command: GRAPH.CONSTRAINT <graph> CREATE <label> <property>
            await redis_client.execute_command("GRAPH.CONSTRAINT", graph_name, "CREATE", label, prop)
            logger.info(f"✅ Applied: {label}.{prop}")
        except Exception as e:
            # Check if error is "constraint already exists"
            if "already exists" in str(e).lower():
                logger.info(f"⚠️  Skipped (Exists): {label}.{prop}")
            else:
                logger.error(f"❌ Failed: {label}.{prop} -> {e}")
                
    await redis_client.close()
    logger.info("Schema application complete.")

if __name__ == "__main__":
    try:
        asyncio.run(apply_schema())
    except KeyboardInterrupt:
        pass
