import logging
import asyncio
from typing import Dict
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from config.settings import Settings
from transport.queue import RedisQueue
from memory.falkordb import FalkorDBProvider
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)

class TelegramBot:
    def __init__(self, settings: Settings, redis_queue: RedisQueue, cognitive_loop = None):
        self.settings = settings
        self.queue = redis_queue
        # self.memory removed (Decoupled)
        self.cognitive_loop = cognitive_loop  # Second Stream: Analysis Loop
        
        # FIX: Force IPv4 to prevent aiohttp hang in Docker
        import socket
        from aiohttp import TCPConnector, ClientSession
        from aiogram.client.session.aiohttp import AiohttpSession
        
        class CustomSession(AiohttpSession):
            async def create_session(self) -> ClientSession:
                connector = TCPConnector(family=socket.AF_INET)
                return ClientSession(connector=connector, json_serialize=self.json_dumps)
        
        session = CustomSession()
        
        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, session=session)
        self.dp = Dispatcher()
        
        # Register handlers
        self.dp.message(CommandStart())(self.cmd_start)
        self.dp.message.register(self.on_message)

    async def cmd_start(self, message: Message):
        """Handle /start command"""
        if str(message.from_user.id) not in self.settings.ALLOWED_USER_IDS:
             await message.answer("Access denied.")
             return
             
        await message.answer("Gemini Observer is online (Async Mode).")

    async def on_message(self, message: types.Message):
        """Receive message and push to Redis Queue (Ingestion)"""
        user_id = str(message.from_user.id)
        
        if user_id not in self.settings.ALLOWED_USER_IDS:
            logging.warning(f"Unauthorized access attempt from {user_id}")
            return

        logging.info(f"Received message from {user_id}: {message.text}")
        
        # Prepare event payload
        event = {
            "chat_id": message.chat.id,
            "user_id": message.from_user.id,
            "text": message.text,
            "timestamp": message.date.isoformat(),
            "message_id": message.message_id,
            "author_name": message.from_user.full_name or "User"
        }
        
        # Push to Queue (Scribe will pick this up)
        await self.queue.push_incoming(event)
        
        # ════════════════════════════════════════════════════════════════
        # SECOND STREAM: Enqueue for Cognitive Analysis (Optional/Legacy)
        # ════════════════════════════════════════════════════════════════
        if self.cognitive_loop and message.text:
            try:
                await self.cognitive_loop.enqueue_message(event)
            except Exception as e:
                logging.error(f"Second Stream Enqueue Error: {e}")

    async def start(self):
        """Start polling"""
        logging.info("Starting Telegram Bot (Receiver)...")
        
        # Debug: Raw aiohttp check
        import aiohttp
        import certifi
        import ssl
        
        # Verify Token
        try:
            logging.info("Verifying Bot Token...")
            bot_info = await self.bot.get_me()
            logging.info(f"Bot Authorized: @{bot_info.username} (ID: {bot_info.id})")
        except Exception as e:
             logging.critical(f"Failed to authorize bot: {e}")
             return

        await self.bot.delete_webhook(drop_pending_updates=True)
        await self.dp.start_polling(self.bot)

    async def stop(self):
        """Close bot session"""
        if self.bot.session:
            await self.bot.session.close()
