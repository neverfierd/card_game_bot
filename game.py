from typing import List, Dict, Tuple, Optional
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram import F


class Card:
    __slots__ = ('suit', 'rank', 'value')
    SUITS = ['♠', '♣', '♦', '♥']
    RANKS = ['6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    VALUES = {r: i + 6 for i, r in enumerate(RANKS)}

    def __init__(self, suit: str, rank: str):
        self.suit = suit
        self.rank = rank
        self.value = self.VALUES[rank]

    def __str__(self):
        return f"{self.rank}{self.suit}"


class FoolGame:
    def __init__(self, players: List[int], bot: Bot):
        self.players = players
        self.bot = bot
        self.deck = self._create_deck()
        self.trump = self.deck[-1]
        self.hands: Dict[int, List[Card]] = {p: [] for p in players}
        self.table: List[Tuple[Card, Optional[Card]]] = []
        self.attacker, self.defender = players[0], players[1]
        self._deal_cards()
        self.last_messages: Dict[int, int] = {}  # Хранение ID последних сообщений

    def _create_deck(self) -> List[Card]:
        return [Card(s, r) for s in Card.SUITS for r in Card.RANKS]

    def _deal_cards(self):
        random.shuffle(self.deck)
        for player in self.players:
            self._fill_hand(player)

    def _fill_hand(self, player_id: int):
        while len(self.hands[player_id]) < 6 and self.deck:
            self.hands[player_id].append(self.deck.pop())

    async def handle_action(self, player_id: int, action: str, callback: CallbackQuery):
        try:
            if player_id == self.attacker:
                await self._handle_attack(player_id, action, callback)
            else:
                await self._handle_defense(player_id, action, callback)
        except Exception as e:
            await callback.answer(f"Ошибка: {str(e)}", show_alert=True)

    async def _handle_attack(self, player_id: int, action: str, callback: CallbackQuery):
        if action == "pass":
            if not self.table:
                await callback.answer("Нельзя пасовать первым ходом!", show_alert=True)
                return
            await self._end_round()
        else:
            card_idx = int(action)
            card = self.hands[player_id][card_idx]

            if self.table and not any(card.rank == c[0].rank for c in self.table):
                await callback.answer("Подкидывать можно только карты того же достоинства!", show_alert=True)
                return

            self.table.append((card, None))
            self.hands[player_id].pop(card_idx)
            await self._update_game()

        await callback.answer()

    async def _handle_defense(self, player_id: int, action: str, callback: CallbackQuery):
        if action == "take":
            await self._take_cards()
        else:
            card_idx = int(action)
            defending_card = self.hands[player_id][card_idx]
            attacking_card = self.table[-1][0]

            if not self._can_beat(attacking_card, defending_card):
                await callback.answer(
                    f"Нужна карта масти {attacking_card.suit} старше {attacking_card.rank} "
                    f"или козырь {self.trump.suit}",
                    show_alert=True
                )
                return

            self.table[-1] = (attacking_card, defending_card)
            self.hands[player_id].pop(card_idx)

            if all(card[1] is not None for card in self.table):
                await self._end_round()

        await callback.answer()
        await self._update_game()

    def _can_beat(self, attack: Card, defense: Card) -> bool:
        return (defense.suit == attack.suit and defense.value > attack.value) or \
            (defense.suit == self.trump.suit and attack.suit != self.trump.suit)

    async def _take_cards(self):
        for attack, defense in self.table:
            self.hands[self.defender].append(attack)
            if defense:
                self.hands[self.defender].append(defense)
        await self._end_round()

    async def _end_round(self):
        self.table = []
        self.attacker, self.defender = self.defender, self.attacker

        for player in self.players:
            self._fill_hand(player)

        if any(not self.hands[p] for p in self.players):
            await self._end_game()
        else:
            await self._update_game()

    async def _end_game(self):
        loser = next(p for p in self.players if not self.hands[p])
        for player in self.players:
            if player == loser:
                await self._send_message(player, "😞 Вы проиграли!")
            else:
                await self._send_message(player, "🎉 Вы победили!")

    async def _update_game(self):
        await self._send_state(self.attacker, is_attacker=True)
        await self._send_state(self.defender, is_attacker=False)

    async def _send_state(self, player_id: int, is_attacker: bool):
        text = f"🃏 Козырь: {self.trump}\n\nВаши карты:\n"
        text += "\n".join(f"{i}. {card}" for i, card in enumerate(self.hands[player_id]))

        if self.table:
            text += "\n\nСтол:\n" + "\n".join(f"{a} → {d if d else '?'}" for a, d in self.table)

        kb = self._create_keyboard(player_id, is_attacker)

        # Удаляем предыдущее сообщение
        if player_id in self.last_messages:
            try:
                await self.bot.delete_message(player_id, self.last_messages[player_id])
            except:
                pass

        # Отправляем новое сообщение и сохраняем его ID
        msg = await self._send_message(player_id, text, reply_markup=kb)
        if msg:
            self.last_messages[player_id] = msg.message_id

    def _create_keyboard(self, player_id: int, is_attacker: bool) -> InlineKeyboardMarkup:
        buttons = []

        if is_attacker:
            for i, card in enumerate(self.hands[player_id]):
                if not self.table or any(card.rank == c[0].rank for c in self.table):
                    buttons.append([InlineKeyboardButton(
                        text=f"{i}. {card}",
                        callback_data=str(i)
                    )])
            if self.table:
                buttons.append([InlineKeyboardButton(
                    text="⏩ Пас",
                    callback_data="pass"
                )])
        else:
            if self.table:
                attack_card = self.table[-1][0]
                for i, card in enumerate(self.hands[player_id]):
                    if self._can_beat(attack_card, card):
                        buttons.append([InlineKeyboardButton(
                            text=f"{i}. {card}",
                            callback_data=str(i)
                        )])
                buttons.append([InlineKeyboardButton(
                    text="🖐 Взять",
                    callback_data="take"
                )])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    async def _send_message(self, chat_id: int, text: str, **kwargs):
        try:
            return await self.bot.send_message(chat_id, text, **kwargs)
        except Exception:
            return None


async def setup_game_handlers(dp: Dispatcher, games: Dict[int, FoolGame]):
    @dp.callback_query(F.data.in_({"pass", "take"}) | F.data.regex(r"^\d+$"))
    async def game_action_handler(callback: CallbackQuery):
        chat_id = callback.message.chat.id
        if chat_id not in games:
            await callback.answer("Игра не найдена")
            return

        await games[chat_id].handle_action(callback.from_user.id, callback.data, callback)
        await callback.answer()

    @dp.message(Command("start_game"))
    async def start_game_handler(message: types.Message):
        chat_id = message.chat.id
        if chat_id in games:
            await message.answer("Игра уже начата!")
            return

        # Здесь должна быть логика создания лобби
        players = [message.from_user.id, 123456789]  # Заглушка для теста
        games[chat_id] = FoolGame(players, dp.bot)
        await message.answer("Игра началась!")
        await games[chat_id]._update_game()