import random
from collections import deque
from typing import List, Optional

# ========================= Core Model ========================= #

class Color:
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    BLUE = "BLUE"
    WILD = "WILD"

    STANDARD = [RED, YELLOW, GREEN, BLUE]

    @staticmethod
    def random_standard():
        return random.choice(Color.STANDARD)


class Rank:
    ZERO = "ZERO"
    ONE = "ONE"
    TWO = "TWO"
    THREE = "THREE"
    FOUR = "FOUR"
    FIVE = "FIVE"
    SIX = "SIX"
    SEVEN = "SEVEN"
    EIGHT = "EIGHT"
    NINE = "NINE"
    SKIP = "SKIP"
    REVERSE = "REVERSE"
    DRAW_TWO = "DRAW_TWO"
    WILD = "WILD"
    WILD_DRAW_FOUR = "WILD_DRAW_FOUR"

    NUMBERS = [ZERO, ONE, TWO, THREE, FOUR, FIVE, SIX, SEVEN, EIGHT, NINE]
    ACTIONS = [SKIP, REVERSE, DRAW_TWO]
    WILDS = [WILD, WILD_DRAW_FOUR]

    @staticmethod
    def is_number(rank):
        return rank in Rank.NUMBERS

    @staticmethod
    def is_action(rank):
        return rank in Rank.ACTIONS

    @staticmethod
    def is_wild(rank):
        return rank in Rank.WILDS


class Card:
    def __init__(self, color: str, rank: str):
        self.color = color
        self.rank = rank

    def matches(self, top_card: 'Card', active_color: str) -> bool:
        if Rank.is_wild(self.rank):
            return True
        if Rank.is_wild(top_card.rank):
            return self.color == active_color or self.rank == top_card.rank
        return self.color == top_card.color or self.rank == top_card.rank

    def __repr__(self):
        if Rank.is_wild(self.rank):
            return f"{self.rank}"
        return f"{self.color} {self.rank}"


# ========================= Deck & Pile ========================= #

class Deck:
    def __init__(self):
        self.draw_pile = deque()
        self.discard_pile = deque()
        self._build()

    def _build(self):
        cards: List[Card] = []
        for c in Color.STANDARD:
            cards.append(Card(c, Rank.ZERO))
            for _ in range(2):
                for r in Rank.NUMBERS[1:] + Rank.ACTIONS:
                    cards.append(Card(c, r))
        for _ in range(4):
            cards.append(Card(Color.WILD, Rank.WILD))
            cards.append(Card(Color.WILD, Rank.WILD_DRAW_FOUR))
        random.shuffle(cards)
        self.draw_pile.extend(cards)

    def draw(self) -> Optional[Card]:
        if not self.draw_pile:
            self._reshuffle_from_discard()
        return self.draw_pile.popleft() if self.draw_pile else None

    def discard(self, card: Card):
        self.discard_pile.appendleft(card)

    def top_discard(self) -> Card:
        return self.discard_pile[0]

    def start_discard_non_wild(self):
        c = None
        while True:
            c = self.draw()
            self.discard(c)
            if not Rank.is_wild(c.rank):
                break

    def _reshuffle_from_discard(self):
        if not self.discard_pile:
            return
        top = self.discard_pile.popleft()
        rest = list(self.discard_pile)
        self.discard_pile.clear()
        random.shuffle(rest)
        self.draw_pile.extend(rest)
        self.discard_pile.appendleft(top)


# ========================= Players ========================= #

class Player:
    def __init__(self, name: str):
        self.name = name
        self.hand: List[Card] = []

    def draw(self, deck: Deck, count: int):
        for _ in range(count):
            c = deck.draw()
            if c:
                self.hand.append(c)

    def has_playable(self, top: Card, active_color: str) -> bool:
        return any(c.matches(top, active_color) for c in self.hand)

    def count_color(self, color: str) -> int:
        return sum(1 for c in self.hand if c.color == color)

    def has_color(self, color: str) -> bool:
        return any((not Rank.is_wild(c.rank)) and c.color == color for c in self.hand)

    def choose_move(self, state: 'GameState') -> 'Move':
        raise NotImplementedError

    def __repr__(self):
        return self.name


class HumanPlayer(Player):
    def __init__(self, name: str):
        super().__init__(name)

    def choose_move(self, state: 'GameState') -> 'Move':
        top = state.deck.top_discard()
        print(f"\nYour turn — Top: [{top}] Active color: {state.active_color}")
        print("Your hand:")
        for i, c in enumerate(self.hand, 1):
            print(f"  {i:2d}) {c}")
        if state.pending_draw > 0:
            print(f"Pending draw to you: {state.pending_draw} (stackable with DRAW_TWO or WILD_DRAW_FOUR)")
        choice = self._read_int("Choose a card number to play, or 0 to draw: ", 0, len(self.hand))
        if choice == 0:
            return Move.draw()
        chosen = self.hand[choice - 1]
        if not chosen.matches(top, state.active_color):
            print("Illegal play. You must match color/rank or play a wild.")
            return Move.invalid()
        chosen_color = state.active_color
        if Rank.is_wild(chosen.rank):
            chosen_color = self._ask_color()
        if state.pending_draw > 0 and chosen.rank not in (Rank.DRAW_TWO, Rank.WILD_DRAW_FOUR):
            print("You must stack with DRAW_TWO or WILD_DRAW_FOUR, or draw.")
            return Move.invalid()
        return Move.play(chosen, chosen_color, False)

    def _read_int(self, prompt: str, min_v: int, max_v: int) -> int:
        while True:
            try:
                v = int(input(prompt).strip())
                if min_v <= v <= max_v:
                    return v
            except Exception:
                pass
            print(f"Enter a number between {min_v} and {max_v}.")

    def _ask_color(self) -> str:
        print("Choose color: 1) RED  2) YELLOW  3) GREEN  4) BLUE")
        m = {1: Color.RED, 2: Color.YELLOW, 3: Color.GREEN, 4: Color.BLUE}
        c = self._read_int("> ", 1, 4)
        return m[c]


class AggressiveAI(Player):
    def __init__(self, name: str):
        super().__init__(name)

    def choose_move(self, state: 'GameState') -> 'Move':
        top = state.deck.top_discard()

        # Stack if pending
        if state.pending_draw > 0:
            stack = self._best_stack_card()
            if stack:
                chosen_color = self._best_color_choice() if Rank.is_wild(stack.rank) else state.active_color
                return Move.play(stack, chosen_color, True)
            return Move.draw()

        # Prefer action cards
        best = None
        for c in self.hand:
            if not c.matches(top, state.active_color):
                continue
            if c.rank == Rank.WILD_DRAW_FOUR:
                legal_wdf = not self.has_color(state.active_color)
                if legal_wdf:
                    return Move.play(c, self._best_color_choice(), True)
                if best is None:
                    best = c
                continue
            if c.rank in (Rank.DRAW_TWO, Rank.SKIP, Rank.REVERSE):
                return Move.play(c, state.active_color, False)
            if best is None:
                best = c

        if best:
            chosen_color = self._best_color_choice() if Rank.is_wild(best.rank) else state.active_color
            return Move.play(best, chosen_color, False)

        return Move.draw()

    def _best_stack_card(self) -> Optional[Card]:
        for c in self.hand:
            if c.rank in (Rank.DRAW_TWO, Rank.WILD_DRAW_FOUR):
                return c
        return None

    def _best_color_choice(self) -> str:
        counts = {
            Color.RED: self.count_color(Color.RED),
            Color.YELLOW: self.count_color(Color.YELLOW),
            Color.GREEN: self.count_color(Color.GREEN),
            Color.BLUE: self.count_color(Color.BLUE),
        }
        return max(counts.items(), key=lambda kv: kv[1])[0]


# ========================= Moves & State ========================= #

class Move:
    PLAY = "PLAY"
    DRAW = "DRAW"
    INVALID = "INVALID"

    def __init__(self, type_: str, card: Optional[Card] = None, chosen_color: Optional[str] = None, challenge: bool = False):
        self.type = type_
        self.card = card
        self.chosen_color = chosen_color
        self.challenge = challenge

    @staticmethod
    def play(card: Card, chosen_color: Optional[str], challenge: bool):
        return Move(Move.PLAY, card, chosen_color, challenge)

    @staticmethod
    def draw():
        return Move(Move.DRAW)

    @staticmethod
    def invalid():
        return Move(Move.INVALID)


class GameState:
    def __init__(self, deck: Deck, players: List[Player], no_mercy: bool):
        self.deck = deck
        self.players = players
        self.current_index = 0
        self.direction = 1
        self.active_color = None
        self.pending_draw = 0
        self.no_mercy = no_mercy

    def current(self) -> Player:
        return self.players[self.current_index]

    def next_player(self) -> Player:
        n = len(self.players)
        idx = (self.current_index + self.direction) % n
        return self.players[idx]

    def advance_turn(self, steps: int):
        n = len(self.players)
        self.current_index = (self.current_index + steps * self.direction) % n

    def reverse(self):
        self.direction *= -1


# ========================= Game Engine ========================= #

class Game:
    def __init__(self, player_count: int = 2, no_mercy: bool = True):
        self.player_count = max(2, player_count)
        self.no_mercy = no_mercy

    def start(self):
        deck = Deck()
        players: List[Player] = [HumanPlayer("You")]
        for i in range(1, self.player_count):
            players.append(AggressiveAI(f"AI-{i}"))
        state = GameState(deck, players, self.no_mercy)

        # Deal
        for p in players:
            p.draw(deck, 7)

        # Start discard
        deck.start_discard_non_wild()
        state.active_color = deck.top_discard().color

        print("UNO — No Mercy Edition (Python)")
        print(f"Players: {[p.name for p in players]}")
        print(f"Starting card: {deck.top_discard()} | Active color: {state.active_color}")

        self._apply_initial_effect(deck.top_discard(), state)

        while True:
            current = state.current()
            print(f"\n--- {current.name}'s turn ---")
            self._show_opponent_hands(state)

            move = current.choose_move(state)
            if move.type == Move.INVALID:
                print("Invalid move. You draw one as penalty.")
                current.draw(state.deck, 1)
                state.advance_turn(1)
                continue

            if move.type == Move.DRAW:
                if state.pending_draw > 0:
                    print(f"{current.name} draws {state.pending_draw} (no stack).")
                    current.draw(state.deck, state.pending_draw)
                    state.pending_draw = 0
                else:
                    drawn = state.deck.draw()
                    print(f"{current.name} draws: {drawn}")
                    if drawn and drawn.matches(state.deck.top_discard(), state.active_color) and state.no_mercy:
                        print(f"{current.name} auto-plays drawn card: {drawn}")
                        current.hand.append(drawn)
                        self._play_card(current, drawn,
                                        self._choose_color_auto(current) if Rank.is_wild(drawn.rank) else state.active_color,
                                        state, False)
                    else:
                        if drawn:
                            current.hand.append(drawn)
                        state.advance_turn(1)
                if self._check_win(current):
                    break
                continue

            # Play
            if move.card not in current.hand:
                print("You don't have that card. Turn forfeited.")
                state.advance_turn(1)
                continue
            if not move.card.matches(state.deck.top_discard(), state.active_color):
                print("Card doesn't match. Turn forfeited.")
                state.advance_turn(1)
                continue

            self._play_card(current, move.card,
                            move.chosen_color if Rank.is_wild(move.card.rank) else state.active_color,
                            state, move.challenge)

            if self._check_win(current):
                break

        print("\nGame over.")

    def _apply_initial_effect(self, start: Card, state: GameState):
        if start.rank == Rank.SKIP:
            print("Start card is SKIP — first player skipped.")
            state.advance_turn(1)
        elif start.rank == Rank.REVERSE:
            print("Start card is REVERSE — direction reversed.")
            state.reverse()
        elif start.rank == Rank.DRAW_TWO:
            print("Start card is DRAW TWO — first player draws 2.")
            state.pending_draw += 2

    def _play_card(self, player: Player, card: Card, chosen_color: Optional[str], state: GameState, challenge_flag: bool):
        player.hand.remove(card)
        state.deck.discard(card)
        if Rank.is_wild(card.rank):
            state.active_color = chosen_color
            print(f"{player.name} plays: {card} → color set to {chosen_color}")
        else:
            print(f"{player.name} plays: {card}")

        if len(player.hand) == 1:
            print(f"{player.name} says UNO!")

        if card.rank == Rank.SKIP:
            print("Next player skipped.")
            state.advance_turn(2)
        elif card.rank == Rank.REVERSE:
            print("Direction reversed.")
            state.reverse()
            if len(state.players) == 2:
                print("Reverse acts as skip with 2 players.")
                state.advance_turn(2)
            else:
                state.advance_turn(1)
        elif card.rank == Rank.DRAW_TWO:
            state.pending_draw += 2
            print(f"Pending draw increased to {state.pending_draw}.")
            state.advance_turn(1)
        elif card.rank == Rank.WILD:
            state.advance_turn(1)
        elif card.rank == Rank.WILD_DRAW_FOUR:
            opponent = state.next_player()
            illegal = self._player_had_active_color_before_wdf(player, state)
            opponent_challenges = isinstance(opponent, AggressiveAI) or challenge_flag

            if opponent_challenges:
                print(f"{opponent.name} challenges the WILD DRAW FOUR!")
                if illegal:
                    print(f"Challenge successful — {player.name} draws 4.")
                    player.draw(state.deck, 4)
                    state.advance_turn(1)
                else:
                    print(f"Challenge failed — {opponent.name} draws 6.")
                    opponent.draw(state.deck, 6)
                    state.advance_turn(1)
            else:
                state.pending_draw += 4
                print(f"Pending draw increased to {state.pending_draw}.")
                state.advance_turn(1)
        else:
            state.advance_turn(1)

    def _player_had_active_color_before_wdf(self, player: Player, state: GameState) -> bool:
        active = state.active_color
        return any((not Rank.is_wild(c.rank)) and c.color == active for c in player.hand)

    def _choose_color_auto(self, player: Player) -> str:
        counts = {
            Color.RED: player.count_color(Color.RED),
            Color.YELLOW: player.count_color(Color.YELLOW),
            Color.GREEN: player.count_color(Color.GREEN),
            Color.BLUE: player.count_color(Color.BLUE),
        }
        return max(counts.items(), key=lambda kv: kv[1])[0]

    def _check_win(self, p: Player) -> bool:
        if not p.hand:
            print(f"\n{p.name} wins!")
            return True
        return False

    def _show_opponent_hands(self, state: GameState):
        for p in state.players:
            if p is state.current():
                continue
            print(f"{p.name} has {len(p.hand)} cards.")


if __name__ == "__main__":
    Game(player_count=2, no_mercy=True).start()
