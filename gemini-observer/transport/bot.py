import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message
from config.settings import settings
from core.loop import RalphLoop

class TelegramBot:
    """
    Transport layer for Telegram.
    Delegates logic to RalphLoop.
    """
    def __init__(self, loop: RalphLoop):
        self.loop = loop
        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher()
        
        # Register handlers
        self.dp.message(CommandStart())(self.cmd_start)
        self.dp.message()(self.handle_message)

    async def start(self):
        """Starts the bot polling."""
        print("Starting Telegram Bot...")
        await self.dp.start_polling(self.bot)

    async def cmd_start(self, message: Message):
        """/start command handler"""
        if message.from_user.id not in settings.ALLOWED_USER_IDS:
             return
        await message.answer("Hello! I am Gemini Observer. Ready to chat.")

    async def handle_message(self, message: Message):
        """Universal message handler"""
        user_id = message.from_user.id
        if user_id not in settings.ALLOWED_USER_IDS:
            logging.warning(f"Unauthorized access attempt from {user_id}")
            return

        # Delegate to Core Loop
        response = await self.loop.process_event(message.text)
        
        # Send response back
        await message.answer(response)
