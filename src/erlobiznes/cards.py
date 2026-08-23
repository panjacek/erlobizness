import random


class Card:
    def __init__(self, text, action):
        self.text = text
        self.action = action  # function(game, player) -> str


def move_to_start(game, player):
    player.position = 0
    player.receive(400)
    return "Move to START and receive 400 $."


def pay_speeding_fine(game, player):
    player.pay(30)
    return "Speeding fine. Pay 30 $."


def hospital_bill(game, player):
    player.pay(100)
    return "Hospital bill. Pay 100 $."


def bank_dividend(game, player):
    player.receive(100)
    return "Bank pays you dividend of 100 $."


def tax_refund(game, player):
    player.receive(20)
    return "Tax refund. Receive 20 $."


def go_to_jail_card(game, player):
    game._send_to_jail(player)
    return "Go to JAIL."


class CardDeck:
    def __init__(self, cards):
        self.cards = cards
        self.reset()

    def reset(self):
        self.deck = self.cards[:]
        random.shuffle(self.deck)

    def draw(self, game, player):
        if not self.deck:
            self.reset()
        card = self.deck.pop(0)
        message = card.action(game, player)
        return f"{card.text}: {message}"


def get_default_red_deck():
    cards = [
        Card("Mandat za szybką jazdę", pay_speeding_fine),
        Card("Bank wypłaca Ci procenty", bank_dividend),
        Card("Wracasz do Startu", move_to_start),
        Card("Idziesz do Więzienia", go_to_jail_card),
        Card("Zwrot podatku", tax_refund),
    ]
    return CardDeck(cards)


def get_default_blue_deck():
    cards = [
        Card("Rachunek za szpital", hospital_bill),
        Card(
            "Płacisz za szkołę", lambda g, p: p.pay(300) or "Pay school fee of 300 $."
        ),
        Card(
            "Wygrana w Totolotka",
            lambda g, p: p.receive(200) or "You won 200 $ in lottery!",
        ),
    ]
    return CardDeck(cards)
