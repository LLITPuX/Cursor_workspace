import asyncio
import logging
import os
from config.settings import settings
from memory.in_memory import InMemoryProvider
from core.gemini_client import GeminiClient
from core.loop import RalphLoop
from transport.bot import TelegramBot

async def main():
    # Logging setup
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Check for credentials before starting (Ignition Check)
    if not os.path.exists(settings.GEMINI_TOKEN_PATH):
        logger.error(f"CRITICAL: Token file not found at {settings.GEMINI_TOKEN_PATH}")
        logger.error("Please run 'python scripts/auth_google.py' locally to generate credentials.")
        return

    logger.info("Initializing components...")

    # 1. Memory
    memory = InMemoryProvider()

    # 2. Client
    try:
        client = GeminiClient()
    except Exception as e:
        logger.error(f"Failed to initialize Gemini Client: {e}")
        return

    # 3. Core Loop
    loop = RalphLoop(memory=memory, client=client)

    # 4. Transport
    bot = TelegramBot(loop=loop)

    # 5. Start
    await bot.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")
