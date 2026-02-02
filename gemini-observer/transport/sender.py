import logging
import asyncio
from aiogram import Bot
from config.settings import Settings
from transport.queue import RedisQueue

class TelegramSender:
    def __init__(self, settings: Settings, redis_queue: RedisQueue):
        self.settings = settings
        self.queue = redis_queue
        
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
                        await self.bot.send_message(chat_id=chat_id, text=text)
                        logging.info(f"Sent message to {chat_id}")
                    else:
                        logging.error(f"Invalid outgoing message format: {message}")
                        
            except Exception as e:
                logging.error(f"Error in sender loop: {e}")
                await asyncio.sleep(1)

    async def stop(self):
        self.running = False
        if self.bot.session:
            await self.bot.session.close()
