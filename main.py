import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from lobby import LobbyManager
from handlers import setup_handlers

logging.basicConfig(level=logging.INFO)

async def main():
    bot = Bot(token="8015063278:AAGoxw-_eUJIMASES1HJ85T89uF9ghLqe_4")
    dp = Dispatcher()

    manager = LobbyManager(bot)
    setup_handlers(dp, manager)

    @dp.message(CommandStart())
    async def start(message: types.Message):
        await message.answer(
            "🎮 Добро пожаловать в игру 'Дурак'!\n\n"
            "Создайте лобби: /create_lobby\n"
            "Присоединитесь: /join <ID_лобби>"
        )

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())