from aiogram import Bot, types
from typing import Dict, List, Optional
import asyncio
from game import FoolGameEngine


class Lobby:
    def __init__(self, lobby_id: int, owner_id: int, bot: Bot):
        self.id = lobby_id
        self.owner = owner_id
        self.players = [owner_id]
        self.bot = bot
        self.game: Optional[FoolGameEngine] = None
        self.last_messages: Dict[int, int] = {}
        self._action_lock = asyncio.Lock()

    async def broadcast(self, text: str, exclude_user: Optional[int] = None):
        for player_id in self.players:
            if player_id != exclude_user:
                try:
                    await self.bot.send_message(player_id, text)
                except Exception as e:
                    print(f"Broadcast error to {player_id}: {e}")

    async def add_player(self, player_id: int) -> bool:
        if player_id in self.players or len(self.players) >= 2:
            return False
        self.players.append(player_id)
        return True

    async def start_game(self) -> bool:
        if len(self.players) == 2:
            self.game = FoolGameEngine(self.players)
            await self._update_ui_all()
            return True
        return False

    async def process_action(self, player_id: int, action: str) -> bool:
        async with self._action_lock:
            if not self.game or player_id not in self.players:
                return False

            success = self.game.process_action(player_id, action)
            if success:
                await self._update_ui_all()
            return success

    async def _update_ui_all(self):
        if not self.game:
            return

        tasks = []
        for player_id in self.players:
            tasks.append(self._update_player_ui(player_id))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _update_player_ui(self, player_id: int):
        try:
            # Получаем состояние с защитой от None
            state = self.game.get_state(player_id) if self.game else {}
            state.setdefault('hand', [])
            state.setdefault('table', [])
            state.setdefault('trump', "♦6")
            state.setdefault('is_my_turn', False)
            state.setdefault('allowed_actions', [])
            state.setdefault('throwable_cards', [])

            # Формируем текст с полной защитой
            hand_text = "\n".join(
                f"{i}. {getattr(card, 'rank', '?')}{getattr(card, 'suit', '?')}"
                for i, card in enumerate(state['hand'])
                if card is not None
            ) or "Нет карт"

            table_text = "\n".join(
                f"{getattr(a, 'rank', '?')}{getattr(a, 'suit', '?')} → "
                f"{getattr(d, 'rank', '?')}{getattr(d, 'suit', '?') if d else '?'}"
                for a, d in state['table']
                if a is not None
            ) or "Стол пуст"

            text = (
                f"🃏 Козырь: {state.get('trump', '♦6')}\n\n"
                f"Ваши карты:\n{hand_text}\n\n"
                f"Стол:\n{table_text}\n\n"
            )

            if state['is_my_turn']:
                text += "✨ Ваш ход!\n"

            if self.game and self.game.is_game_over():
                winner = self.game.get_winner()
                text += f"🎉 Игра окончена! {'Ничья!' if winner is None else f'Победитель: {winner}'}"

            kb = self._create_keyboard(player_id, state)

            try:
                if player_id in self.last_messages:
                    await self.bot.delete_message(player_id, self.last_messages[player_id])
            except:
                pass

            msg = await self.bot.send_message(
                chat_id=player_id,
                text=text,
                reply_markup=kb
            )
            self.last_messages[player_id] = msg.message_id

        except Exception as e:
            print(f"Ошибка UI (fixed): {player_id} - {str(e)}")
            try:
                await self.bot.send_message(
                    chat_id=player_id,
                    text="♻ Обновление интерфейса..."
                )
            except:
                pass

    def _create_keyboard(self, player_id: int, state: dict) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[])

        state.setdefault('hand', [])
        state.setdefault('allowed_actions', [])

        card_buttons = []
        for i, card in enumerate(state['hand']):
            if card is None:
                continue

            card_text = f"{getattr(card, 'rank', '?')}{getattr(card, 'suit', '?')}"

            if str(i) in state['allowed_actions']:
                card_buttons.append(
                    types.InlineKeyboardButton(
                        text=card_text,
                        callback_data=f"play_{i}"
                    )
                )

        if card_buttons:
            kb.inline_keyboard.append(card_buttons)

        action_buttons = []

        if ("pass" in state.get('allowed_actions', []) and
                state.get('is_my_turn', False)):
            action_buttons.append(
                types.InlineKeyboardButton(
                    text="✅ Бито (все покрыто)",
                    callback_data="play_pass"
                )
            )

        if "take" in state.get('allowed_actions', []):
            action_buttons.append(
                types.InlineKeyboardButton(
                    text="🖐 Взять карты",
                    callback_data="play_take"
                )
            )

        action_buttons.append(
            types.InlineKeyboardButton(
                text="🚪 Выйти",
                callback_data="lobby_leave"
            )
        )

        if action_buttons:
            kb.inline_keyboard.append(action_buttons)

        return kb


class LobbyManager:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.lobbies: Dict[int, Lobby] = {}
        self.user_lobbies: Dict[int, int] = {}

    async def create_lobby(self, owner_id: int, lobby_id: Optional[int] = None) -> Optional[Lobby]:
        if owner_id in self.user_lobbies:
            return None

        if lobby_id is None:
            lobby_id = len(self.lobbies) + 1

        if lobby_id in self.lobbies:
            return None

        self.lobbies[lobby_id] = Lobby(lobby_id, owner_id, self.bot)
        self.user_lobbies[owner_id] = lobby_id
        return self.lobbies[lobby_id]

    async def join_lobby(self, player_id: int, lobby_id: int) -> bool:
        if lobby_id not in self.lobbies or player_id in self.user_lobbies:
            return False

        lobby = self.lobbies[lobby_id]
        if await lobby.add_player(player_id):
            self.user_lobbies[player_id] = lobby_id
            return True
        return False

    def get_user_lobby(self, user_id: int) -> Optional[Lobby]:
        return self.lobbies.get(self.user_lobbies.get(user_id))

    async def delete_lobby(self, lobby_id: int) -> bool:
        if lobby_id not in self.lobbies:
            return False

        lobby = self.lobbies[lobby_id]
        for player_id in lobby.players:
            if player_id in self.user_lobbies:
                del self.user_lobbies[player_id]

        del self.lobbies[lobby_id]
        return True
