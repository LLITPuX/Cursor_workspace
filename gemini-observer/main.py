import asyncio
import logging
import redis.asyncio as redis
from config.settings import settings
from memory.falkordb import FalkorDBProvider
from transport.queue import RedisQueue
from transport.telegram_bot import TelegramBot
from transport.sender import TelegramSender
from core.loop import RalphLoop
from core.analysis_loop import CognitiveLoop
from core.researcher import Researcher
from core.providers.gemini_provider import GeminiProvider

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def main():
    logging.info("🚀 SYSTEM IGNITION: Initializing Synapse Phase...")

    # 1. Shared Async Connection Pool
    # Note: We use the hostname 'falkordb' for Docker networking.
    redis_url = f"redis://{settings.FALKORDB_HOST}:{settings.FALKORDB_PORT}"
    logging.info(f"Connecting to Redis/FalkorDB at {redis_url}...")
    
    redis_client = redis.from_url(redis_url, encoding="utf-8", decode_responses=False)
    
    # 2. Init Shared Components
    redis_queue = RedisQueue(
        redis_client=redis_client,
        incoming_key=settings.REDIS_QUEUE_INCOMING,
        outgoing_key=settings.REDIS_QUEUE_OUTGOING
    )
    
    memory_provider = FalkorDBProvider(redis_client=redis_client)
    # NOTE: Genesis Nodes (User, Agent, Chat, Year, Day) are pre-created

    # 3. Initialize Logic Core (First Stream - Brain)
    gemini_provider = None
    try:
        gemini_provider = GeminiProvider()
        logging.info("Gemini Provider Initialized.")
    except Exception as e:
        logging.critical(f"Failed to initialize Gemini Provider: {e}")
    
    ralph_loop = RalphLoop(
        memory=memory_provider,
        client=gemini_provider,
        queue=redis_queue
    )
    
    # ═══════════════════════════════════════════════════════════════════════
    # 4. Initialize Researcher & Cognitive Loop (Second Stream)
    # ═══════════════════════════════════════════════════════════════════════
    researcher = Researcher(
        switchboard=ralph_loop.switchboard,
        memory_provider=memory_provider
    )
    logging.info("Researcher Tool initialized")
    
    # Inject Researcher into RalphLoop for RAG
    ralph_loop.set_researcher(researcher)

    cognitive_loop = CognitiveLoop(
        redis_client=redis_client,
        switchboard=ralph_loop.switchboard,  # Reuse Switchboard from RalphLoop
        memory_provider=memory_provider,
        researcher=researcher
    )
    logging.info("CognitiveLoop (Second Stream) initialized")

    # 5. Initialize Transport
    telegram_bot = TelegramBot(
        settings=settings, 
        redis_queue=redis_queue, 
        memory=memory_provider,
        cognitive_loop=cognitive_loop  # Pass for Second Stream enqueue
    )
    telegram_sender = TelegramSender(settings=settings, redis_queue=redis_queue, memory=memory_provider)

    # 6. Launch Parallel Tasks
    logging.info("Launching parallel services...")
    
    tasks = []
    
    # Task A: Listener (Polling)
    tasks.append(asyncio.create_task(telegram_bot.start()))
    
    # Task B: First Stream - Brain (Chat Responses)
    tasks.append(asyncio.create_task(ralph_loop.run_worker()))
    
    # Task C: Sender (Worker)
    tasks.append(asyncio.create_task(telegram_sender.start()))
    
    # Task D: Second Stream - Cognitive Loop (Background Analysis)
    tasks.append(asyncio.create_task(cognitive_loop.start()))

    logging.info("🚀 SYSTEM ONLINE. All systems go.")
    logging.info("📊 Streams: First (Brain) + Second (Cognitive Loop)")
    
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        await telegram_bot.stop()
        await telegram_sender.stop()
        await ralph_loop.stop()
        await cognitive_loop.stop()
        await redis_client.close()
        logging.info("System halted.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
