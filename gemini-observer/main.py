import asyncio
import logging
import redis.asyncio as redis
import os

from config.settings import settings
from memory.falkordb import FalkorDBProvider
from transport.queue import RedisQueue
from transport.telegram_bot import TelegramBot
from transport.sender import TelegramSender

# Core Components
from core.switchboard import Switchboard
from core.providers.gemini_provider import GeminiProvider
from core.providers.openai_provider import OpenAIProvider
from core.providers.ollama_provider import OllamaProvider
from core.researcher import Researcher
from core.memory.prompt_builder import GraphPromptBuilder

# Streams
from streams.scribe import Scribe
from streams.thinker import Thinker
from streams.analyst import Analyst
from streams.coordinator import Coordinator
from streams.responder import Responder

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def main():
    logging.info("🚀 SYSTEM IGNITION: Stream Architecture V2 (Local Cortex)...")

    # 1. Connection Pool
    redis_url = f"redis://{settings.FALKORDB_HOST}:{settings.FALKORDB_PORT}"
    logging.info(f"Connecting to Redis/FalkorDB at {redis_url}...")
    
    redis_client = redis.from_url(redis_url, encoding="utf-8", decode_responses=False)
    
    # 2. Memory & Queues
    memory_provider = FalkorDBProvider(redis_client=redis_client)
    
    # GraphPromptBuilder (reads from GeminiStream graph)
    prompt_builder = GraphPromptBuilder(redis_client=redis_client)
    
    # Unified Queue Wrapper (Note: each stream uses specific keys from settings)
    # We pass the same RedisQueue instance or create separate ones, 
    # but since RediqueQueue implementation is generic and keys are passed to methods, 
    # we can mostly reuse the client connection.
    # However, existing streams expect a RedisQueue object which has specific 'incoming/outgoing' keys baked in? 
    # Let's check RedisQueue implementation. 
    # It seems Scribe and Bot use 'incoming_key' and 'outgoing_key'.
    # New streams use explicit keys in their start() loops via settings.
    
    # Queue for Ingress (Bot -> Scribe)
    redis_queue_ingress = RedisQueue(
        redis_client=redis_client,
        incoming_key=settings.REDIS_QUEUE_INCOMING,
        outgoing_key=settings.REDIS_QUEUE_OUTGOING
    )
    
    # 3. Switchboard (Intelligence Core)
    # Fast (Ollama)
    fast_provider = OllamaProvider(host="http://falkordb-ollama:11434", model="gemma3:4b")
    
    # Primary (Gemini or OpenAI)
    # We try Gemini first
    try:
        gemini_provider = GeminiProvider()
        logging.info("🌟 Primary Provider: Gemini")
        primary_provider = gemini_provider
    except Exception as e:
        logging.warning(f"Gemini not available: {e}")
        primary_provider = fast_provider # Fallback if init fails

    # Secondary (OpenAI)
    fallback_provider = fast_provider
    if settings.OPENAI_API_KEY:
         fallback_provider = OpenAIProvider(model="gpt-4o-mini", api_key=settings.OPENAI_API_KEY)
         logging.info("🛡️ Fallback Provider: OpenAI")

    switchboard = Switchboard(
        primary=primary_provider,
        fallback=fallback_provider,
        fast=fast_provider,
        graph_logger=memory_provider
    )
    
    # 4. Tools
    researcher = Researcher(switchboard=switchboard, memory_provider=memory_provider)

    # 5. Initialize Streams
    
    # Stream 1: Scribe (Ingest -> Graph -> Brain Queue)
    scribe = Scribe(redis_queue=redis_queue_ingress, memory=memory_provider)
    
    # Stream 2: Thinker (Brain Queue -> Narrative -> Analyst Queue)
    thinker = Thinker(redis_queue=redis_queue_ingress, memory=memory_provider, switchboard=switchboard, prompt_builder=prompt_builder)
    
    # Stream 3: Analyst (Analyst Queue -> Plan -> Coordinator Queue)
    analyst = Analyst(redis_queue=redis_queue_ingress, memory=memory_provider, switchboard=switchboard, prompt_builder=prompt_builder)
    
    # Stream 4: Coordinator (Coordinator Queue -> Action -> Responder Queue)
    coordinator = Coordinator(redis_queue=redis_queue_ingress, memory=memory_provider, researcher=researcher)
    
    # Stream 5: Responder (Responder Queue -> Text -> Outgoing Queue)
    responder = Responder(redis_queue=redis_queue_ingress, memory=memory_provider, switchboard=switchboard, prompt_builder=prompt_builder)

    # 6. Transport Layer
    # TelegramBot puts messages into Ingestion Queue
    # logic_loop=None because we don't have a monolithic loop anymore
    telegram_bot = TelegramBot(
        settings=settings, 
        redis_queue=redis_queue_ingress, 
        cognitive_loop=None 
    )
    
    # TelegramSender reads from Outgoing Queue
    telegram_sender = TelegramSender(settings=settings, redis_queue=redis_queue_ingress, memory=memory_provider)

    # 7. Launch Parallel Tasks
    logging.info("🌊 Launching Stream Pipeline...")
    
    tasks = [
        asyncio.create_task(telegram_bot.start(), name="TelegramBot"),
        asyncio.create_task(scribe.start(), name="Stream-1-Scribe"),
        asyncio.create_task(thinker.start(), name="Stream-2-Thinker"),
        asyncio.create_task(analyst.start(), name="Stream-3-Analyst"),
        asyncio.create_task(coordinator.start(), name="Stream-4-Coordinator"),
        asyncio.create_task(responder.start(), name="Stream-5-Responder"),
        asyncio.create_task(telegram_sender.start(), name="TelegramSender")
    ]
    
    logging.info(f"🚀 SYSTEM ONLINE. {len(tasks)} active tasks.")
    
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        await telegram_bot.stop()
        await scribe.stop()
        await thinker.stop()
        await analyst.stop()
        await coordinator.stop()
        await responder.stop()
        await telegram_sender.stop()
        await redis_client.close()
        logging.info("System halted.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
