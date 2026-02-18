import logging
import asyncio
from datetime import datetime
from aiogram import Bot
from config.settings import Settings
from transport.queue import RedisQueue
from memory.falkordb import FalkorDBProvider

class TelegramSender:
    def __init__(self, settings: Settings, redis_queue: RedisQueue, memory: FalkorDBProvider = None):
        self.settings = settings
        self.queue = redis_queue
        self.memory = memory  # First Stream: Graph Memory
        
        # FIX: Force IPv4 for Sender as well
        import socket
        from aiohttp import TCPConnector, ClientSession
        from aiogram.client.session.aiohttp import AiohttpSession
        
        class CustomSession(AiohttpSession):
            async def create_session(self) -> ClientSession:
                connector = TCPConnector(family=socket.AF_INET)
                return ClientSession(connector=connector, json_serialize=self.json_dumps)
        
        session = CustomSession()
        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, session=session)
        self.running = False

    async def start(self):
        """Start consumption loop"""
        self.running = True
        logging.info("Starting Telegram Sender...")
        
        while self.running:
            try:
                # Pop message from outgoing queue
                message = await self.queue.pop_outgoing(timeout=2)
                
                if message:
                    chat_id = message.get("chat_id")
                    text = message.get("text")
                    
                    if chat_id and text:
                        # Telegram limit: 4096 chars per message
                        MAX_LEN = 4096
                        chunks = [text[i:i+MAX_LEN] for i in range(0, len(text), MAX_LEN)]
                        
                        sent_msg = None
                        for chunk in chunks:
                            sent_msg = await self.bot.send_message(chat_id=chat_id, text=chunk)
                        
                        logging.info(f"Sent message to {chat_id} (msg_id: {sent_msg.message_id}, chunks: {len(chunks)})")
                        
                        # ════════════════════════════════════════════════════════════════
                        # FIRST STREAM (The Scribe): Save agent response to Graph
                        # ════════════════════════════════════════════════════════════════
                        if self.memory:
                            try:
                                await self.memory.save_agent_response(
                                    agent_telegram_id=self.settings.BOT_TELEGRAM_ID,
                                    chat_id=chat_id,
                                    message_id=sent_msg.message_id,
                                    text=text,
                                    timestamp=datetime.now()
                                )
                            except Exception as e:
                                logging.error(f"First Stream (Agent) Error: {e}")
                    else:
                        logging.error(f"Invalid outgoing message format: {message}")
                        
            except Exception as e:
                logging.error(f"Error in sender loop: {e}")
                await asyncio.sleep(1)

    async def stop(self):
        self.running = False
        if self.bot.session:
            await self.bot.session.close()
