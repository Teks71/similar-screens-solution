import asyncio
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart

BOT_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"

async def main() -> None:
    token = os.environ.get(BOT_TOKEN_ENV)
    if not token:
        raise RuntimeError(f"Set {BOT_TOKEN_ENV} env var with Telegram bot token")

    bot = Bot(token=token)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def cmd_start(message: types.Message):
        await message.answer("Привет! Я бот проекта similar-screens-solution.")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
