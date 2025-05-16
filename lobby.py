from aiogram import Bot, Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from typing import Dict, List, Optional
from game import FoolGame

router = Router()


class Lobby:
    def __init__(self, lobby_id: int, owner_id: int, bot: Bot):
        self.id = lobby_id
        self.owner = owner_id
        self.players = [owner_id]
        self.bot = bot
        self.game: Optional[FoolGame] = None

    async def broadcast(self, text: str, exclude_user: Optional[int] = None):
        for player_id in self.players:
            if player_id != exclude_user:
                await self.bot.send_message(player_id, text)

    async def start_game(self):
        if len(self.players) == 2:
            self.game = FoolGame(self.players, self.bot)
            await self.broadcast(f"🎮 Игра в дурака началась! Козырь: {self.game.trump}")
            await self.game.start()


class LobbyManager:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.lobbies: Dict[int, Lobby] = {}
        self.user_lobbies: Dict[int, int] = {}  # user_id: lobby_id

    def create_lobby(self, owner_id: int) -> Optional[Lobby]:
        if owner_id in self.user_lobbies:
            return None

        lobby_id = len(self.lobbies) + 1
        self.lobbies[lobby_id] = Lobby(lobby_id, owner_id, self.bot)
        self.user_lobbies[owner_id] = lobby_id
        return self.lobbies[lobby_id]

    def delete_lobby(self, lobby_id: int) -> bool:
        if lobby_id not in self.lobbies:
            return False

        lobby = self.lobbies[lobby_id]
        for player_id in lobby.players:
            if player_id in self.user_lobbies:
                del self.user_lobbies[player_id]

        del self.lobbies[lobby_id]
        return True

    def get_user_lobby(self, user_id: int) -> Optional[Lobby]:
        lobby_id = self.user_lobbies.get(user_id)
        return self.lobbies.get(lobby_id) if lobby_id else None


def setup_lobby_handlers(router: Router, manager: LobbyManager):
    @router.message(Command("create_lobby"))
    async def create_lobby_handler(message: types.Message):
        if manager.get_user_lobby(message.from_user.id):
            await message.answer("❌ У вас уже есть активное лобби!")
            return

        lobby = manager.create_lobby(message.from_user.id)
        if not lobby:
            await message.answer("❌ Ошибка создания лобби")
            return

        await message.answer(
            f"🎮 Лобби {lobby.id} создано!\n"
            f"Пригласите друга: /join {lobby.id}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Пригласить", url=f"tg://msg?text=/join {lobby.id}")]
            ])
        )

    @router.message(Command("delete_lobby"))
    async def delete_lobby_handler(message: types.Message):
        lobby = manager.get_user_lobby(message.from_user.id)
        if not lobby:
            await message.answer("❌ У вас нет активного лобби")
            return

        if lobby.owner != message.from_user.id:
            await message.answer("❌ Только создатель может удалить лобби")
            return

        manager.delete_lobby(lobby.id)
        await message.answer("✅ Лобби удалено")

    @router.message(Command("join"))
    async def join_lobby_handler(message: types.Message):
        try:
            lobby_id = int(message.text.split()[1])
            lobby = manager.lobbies.get(lobby_id)

            if not lobby:
                await message.answer("❌ Лобби не найдено!")
                return

            if message.from_user.id in lobby.players:
                await message.answer("ℹ️ Вы уже в этом лобби!")
                return

            if len(lobby.players) >= 2:
                await message.answer("❌ Лобби уже заполнено!")
                return

            lobby.players.append(message.from_user.id)
            manager.user_lobbies[message.from_user.id] = lobby_id

            await lobby.broadcast(
                f"🎉 Игрок {message.from_user.full_name} присоединился!",
                exclude_user=message.from_user.id
            )
            await message.answer(
                f"✅ Вы в лобби {lobby_id}\n"
                f"Ожидаем второго игрока для старта игры /start_game"
            )
        except (IndexError, ValueError):
            await message.answer("ℹ️ Используйте: /join <ID_лобби>")

    @router.message(Command("start_game"))
    async def start_game_handler(message: types.Message):
        lobby = manager.get_user_lobby(message.from_user.id)
        if not lobby:
            await message.answer("❌ Вы не в лобби!")
            return

        if len(lobby.players) < 2:
            await message.answer("❌ Нужно 2 игрока для начала игры!")
            return

        await lobby.start_game()

    @router.callback_query(F.data.startswith(("attack_", "defend_", "pass", "take")))
    async def game_action_handler(callback: CallbackQuery):
        lobby = manager.get_user_lobby(callback.from_user.id)
        if not lobby or not lobby.game:
            await callback.answer("Действие недоступно", show_alert=True)
            return

        try:
            await lobby.game.process_action(callback.from_user.id, callback.data)
        except Exception as e:
            await callback.answer(f"Ошибка: {str(e)}", show_alert=True)

    @router.message()
    async def lobby_chat_handler(message: types.Message):
        lobby = manager.get_user_lobby(message.from_user.id)
        if not lobby:
            await message.answer("ℹ️ Вы не в лобби. Создайте: /create_lobby")
            return

        if lobby.game:
            return  # Игровые действия обрабатываются через кнопки

        await lobby.broadcast(
            f"{message.from_user.full_name}: {message.text}",
            exclude_user=message.from_user.id
        )