import asyncio
import logging
import redis.asyncio as redis
from config.settings import settings
from memory.falkordb import FalkorDBProvider
from transport.queue import RedisQueue
from transport.telegram_bot import TelegramBot
from transport.sender import TelegramSender
from core.loop import RalphLoop
from core.providers.gemini_provider import GeminiProvider

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def main():
    logging.info("🚀 SYSTEM IGNITION: Initializing Synapse Phase...")

    # 1. Shared Async Connection Pool
    # Note: We use the hostname 'falkordb' for Docker networking.
    redis_url = f"redis://{settings.FALKORDB_HOST}:{settings.FALKORDB_PORT}"
    logging.info(f"Connecting to Redis/FalkorDB at {redis_url}...")
    
    redis_client = redis.from_url(redis_url, encoding="utf-8", decode_responses=False) # decode_responses=False because FalkorDB might return bytes or we handle it in provider
    
    # 2. Init Shared Components
    redis_queue = RedisQueue(
        redis_client=redis_client,
        incoming_key=settings.REDIS_QUEUE_INCOMING,
        outgoing_key=settings.REDIS_QUEUE_OUTGOING
    )
    
    memory_provider = FalkorDBProvider(redis_client=redis_client)
    # NOTE: Genesis Nodes (User, Agent, Chat, Year, Day) are pre-created and must be preserved

    # 3. Initialize Logic Core
    gemini_provider = None
    try:
        gemini_provider = GeminiProvider()
        logging.info("Gemini Provider Initialized.")
    except Exception as e:
        logging.critical(f"Failed to initialize Gemini Provider: {e}")
        # We continue, but the brain might fail.
    
    ralph_loop = RalphLoop(
        memory=memory_provider,
        client=gemini_provider,
        queue=redis_queue
    )

    # 4. Initialize Transport
    # Note: TelegramBot and TelegramSender now just accept the prepared queue
    telegram_bot = TelegramBot(settings=settings, redis_queue=redis_queue, memory=memory_provider)
    telegram_sender = TelegramSender(settings=settings, redis_queue=redis_queue, memory=memory_provider)

    # 5. Launch Parallel Tasks
    logging.info("Launching parallel services...")
    
    tasks = []
    
    # Task A: Listener (Polling)
    # Note: TelegramBot.start() is the polling loop
    tasks.append(asyncio.create_task(telegram_bot.start()))
    
    # Task B: Brain (Loop)
    tasks.append(asyncio.create_task(ralph_loop.run_worker()))
    
    # Task C: Sender (Worker)
    tasks.append(asyncio.create_task(telegram_sender.start()))

    logging.info("🚀 SYSTEM ONLINE. All systems go.")
    
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        await telegram_bot.stop()
        await telegram_sender.stop()
        await ralph_loop.stop()
        await redis_client.close()
        logging.info("System halted.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
