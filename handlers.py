from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


def setup_handlers(router: Router, manager: 'LobbyManager'):
    @router.message(Command("create_lobby"))
    async def create_lobby(message: types.Message):
        lobby = await manager.create_lobby(message.from_user.id)
        if not lobby:
            await message.answer("❌ У вас уже есть активное лобби!")
            return

        await message.answer(
            f"🎮 Лобби {lobby.id} создано!\n"
            f"Пригласите друга: /join {lobby.id}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="Пригласить",
                    url=f"tg://msg?text=/join {lobby.id}"
                )]
            ])
        )

    @router.message(Command("join"))
    async def join_lobby(message: types.Message):
        try:
            lobby_id = int(message.text.split()[1])
            success = await manager.join_lobby(message.from_user.id, lobby_id)

            if not success:
                await message.answer("❌ Не удалось присоединиться к лобби")
                return

            lobby = manager.get_user_lobby(message.from_user.id)
            await lobby.broadcast(
                f"🎉 Игрок {message.from_user.full_name} присоединился!",
                exclude_user=message.from_user.id
            )

            await message.answer(
                f"✅ Вы в лобби {lobby_id}\n"
                f"Игроков: {len(lobby.players)}/2\n"
                f"Для начала игры: /start_game"
            )
        except (IndexError, ValueError):
            await message.answer("ℹ️ Используйте: /join <ID_лобби>")

    @router.message(Command("start_game"))
    async def start_game(message: types.Message):
        lobby = manager.get_user_lobby(message.from_user.id)
        if not lobby:
            await message.answer("❌ Вы не в лобби!")
            return

        if len(lobby.players) < 2:
            await message.answer("❌ Нужно 2 игрока для начала игры!")
            return

        if await lobby.start_game():
            await message.answer("🎮 Игра началась!")
        else:
            await message.answer("❌ Не удалось начать игру")

    @router.callback_query(F.data.startswith("play_"))
    async def game_action(callback: types.CallbackQuery):
        try:
            lobby = manager.get_user_lobby(callback.from_user.id)
            if not lobby or not lobby.game:
                await callback.answer("Игра не найдена")
                return

            action = callback.data.replace("play_", "")
            if not action:
                await callback.answer("Неверное действие")
                return

            success = await lobby.process_action(callback.from_user.id, action)

            if success:
                await lobby._update_ui_all()
                await callback.answer()
            else:
                await callback.answer("Недопустимое действие!", show_alert=True)
        except Exception as e:
            print(f"Game action error: {e}")
            await callback.answer("Ошибка обработки действия", show_alert=True)

    @router.message()
    async def lobby_chat(message: types.Message):
        lobby = manager.get_user_lobby(message.from_user.id)
        if not lobby:
            await message.answer("ℹ️ Вы не в лобби. Создайте: /create_lobby")
            return

        if lobby.game:
            return

        await lobby.broadcast(
            f"{message.from_user.full_name}: {message.text}",
            exclude_user=message.from_user.id
        )
