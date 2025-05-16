from typing import List, Dict, Tuple, Optional
import random
from dataclasses import dataclass


@dataclass
class Card:
    suit: str
    rank: str
    value: int


class FoolGameEngine:
    SUITS = ['♠', '♣', '♦', '♥']
    RANKS = ['6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

    def __init__(self, players: List[int]):
        self.players = players
        self.deck = self._create_deck()
        self.trump = self.deck[-1] if self.deck else Card('♦', '6', 6)
        self.hands: Dict[int, List[Card]] = {p: [] for p in players}
        self.table: List[Tuple[Card, Optional[Card]]] = []
        self.attacker, self.defender = players[0], players[1]
        self._deal_cards()

    def _create_deck(self) -> List[Card]:
        values = {r: i + 6 for i, r in enumerate(self.RANKS)}
        deck = [Card(s, r, values[r]) for s in self.SUITS for r in self.RANKS]
        if not deck:
            raise ValueError("Не удалось создать колоду карт")
        return deck

    def _deal_cards(self):
        if not self.deck:
            self.deck = self._create_deck()
        random.shuffle(self.deck)
        for player in self.players:
            self._fill_hand(player)

    def _fill_hand(self, player_id: int):
        while len(self.hands[player_id]) < 6 and self.deck:
            card = self.deck.pop()
            if card:  # Проверка на None
                self.hands[player_id].append(card)

    def get_state(self, player_id: int) -> Dict:
        """Возвращает безопасное состояние игры"""
        trump_text = f"{self.trump.rank}{self.trump.suit}" if self.trump else "♦6"
        return {
            'hand': [c for c in self.hands.get(player_id, []) if c],
            'table': [(a, d) for a, d in self.table if a],
            'trump': trump_text,
            'is_my_turn': player_id == self.attacker,
            'allowed_actions': self._get_allowed_actions(player_id),
            'players': self.players
        }

    def _get_allowed_actions(self, player_id: int) -> List[str]:
        actions = []
        if player_id not in self.hands:
            return actions

        if player_id == self.attacker:
            for i, card in enumerate(self.hands[player_id]):
                if card and (not self.table or any(card.rank == c[0].rank for c in self.table if c[0])):
                    actions.append(str(i))
            if self.table:
                actions.append("pass")
        elif self.table:
            attack_card = self.table[-1][0] if self.table else None
            if attack_card:
                for i, card in enumerate(self.hands[player_id]):
                    if card and self._can_beat(attack_card, card):
                        actions.append(str(i))
                actions.append("take")
        return actions

    def _can_beat(self, attack: Card, defense: Card) -> bool:
        if not attack or not defense:
            return False
        return (defense.suit == attack.suit and defense.value > attack.value) or \
            (defense.suit == self.trump.suit and attack.suit != self.trump.suit)

    def process_action(self, player_id: int, action: str) -> bool:
        try:
            if player_id == self.attacker:
                return self._process_attack(player_id, action)
            return self._process_defense(player_id, action)
        except Exception as e:
            print(f"Action error: {e}")
            return False

    def _process_attack(self, player_id: int, action: str) -> bool:
        if action == "pass":
            if not self.table:
                return False
            self._end_round()
            return True

        try:
            card_idx = int(action)
            if 0 <= card_idx < len(self.hands[player_id]):
                card = self.hands[player_id][card_idx]
                if card and (not self.table or any(card.rank == c[0].rank for c in self.table if c[0])):
                    self.table.append((card, None))
                    self.hands[player_id].pop(card_idx)
                    return True
        except (ValueError, IndexError):
            pass
        return False

    def _process_defense(self, player_id: int, action: str) -> bool:
        if not self.table:
            return False

        if action == "take":
            self._take_cards()
            return True

        try:
            card_idx = int(action)
            if 0 <= card_idx < len(self.hands[player_id]):
                defending_card = self.hands[player_id][card_idx]
                attacking_card = self.table[-1][0]

                if defending_card and attacking_card and self._can_beat(attacking_card, defending_card):
                    self.table[-1] = (attacking_card, defending_card)
                    self.hands[player_id].pop(card_idx)

                    if all(card[1] is not None for card in self.table):
                        self._end_round()
                    return True
        except (ValueError, IndexError):
            pass
        return False

    def _take_cards(self):
        for attack, defense in self.table:
            if attack:
                self.hands[self.defender].append(attack)
                if defense:
                    self.hands[self.defender].append(defense)
        self._end_round()

    def _end_round(self):
        self.table = []
        self.attacker, self.defender = self.defender, self.attacker
        for p in self.players:
            self._fill_hand(p)

    def is_game_over(self) -> bool:
        return any(not self.hands.get(p, []) for p in self.players)

    def get_winner(self) -> Optional[int]:
        for p in self.players:
            if not self.hands.get(p, []):
                return p
        return None