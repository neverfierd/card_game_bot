import logging
import asyncio
from aiogram import Bot, Dispatcher
from lobby import LobbyManager
from handlers import setup_handlers

logging.basicConfig(level=logging.INFO)


async def main():
    bot = Bot(token="8015063278:AAGoxw-_eUJIMASES1HJ85T89uF9ghLqe_4")
    dp = Dispatcher()

    manager = LobbyManager(bot)
    setup_handlers(dp, manager)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
