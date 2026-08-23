from . import player, cards
from .board import Board
from .dice import Dice
from .lang_pl import MESSAGES

SAVE_VERSION = 1


class ErloGame:
    def __init__(self):
        self.login_players()
        self.board = Board()
        self.dice = Dice()
        self.red_deck = cards.get_default_red_deck()
        self.blue_deck = cards.get_default_blue_deck()
        self.game_over = False
        self.active_trade = None
        self.pending_purchase = None
        self.last_roll = None
        self.last_moves = []

    def login_players(self):
        # TODO: implement proper player login
        self.players = [player.Player("Jo"), player.Player("Zed")]

    def _get_owned_in_group(self, owner, field_type, country=None):
        count = 0
        for prop in owner.properties:
            if prop["type"] == field_type:
                if country is None or prop.get("country") == country:
                    count += 1
        return count

    def _is_group_complete(self, owner, country):
        if not country:
            return False
        total_in_country = sum(
            1 for f in self.board.fields if f.get("country") == country
        )
        owned_in_country = self._get_owned_in_group(owner, "city", country)
        return total_in_country == owned_in_country

    def _send_to_jail(self, p):
        p.in_jail = True
        p.position = 10
        p.jail_turns = 0

    def play_turn(self, p):
        results = []
        self.last_moves = []
        results.append(MESSAGES["turn_start"].format(name=p.name))

        if p.in_jail:
            escaped, msg = p.attempt_jail_escape()
            results.append(msg)
            if not escaped:
                return results
            results.append(MESSAGES["jail_free"].format(name=p.name))

        # Doubles grant an extra roll; second consecutive double -> jail
        # (official Eurobiznes rule, see docs/eurobiznes_rules.md)
        doubles = 0
        while True:
            d1, d2 = self.dice.roll(), self.dice.roll()
            is_double = d1 == d2
            doubles = doubles + 1 if is_double else 0
            steps = d1 + d2
            self.last_roll = {"total": steps, "rolls": [[d1, d2]]}
            rolls_desc = f"({d1},{d2})"

            if doubles == 2:
                results.append(
                    MESSAGES["rolled_doubles_jail"].format(
                        name=p.name, rolls=rolls_desc
                    )
                )
                self._send_to_jail(p)
                return results

            start = p.position
            cross, new_pos = p.walk(steps, len(self.board.fields))
            self.last_moves.append(
                {"roll": dict(self.last_roll), "start": start, "end": new_pos}
            )
            results.append(
                MESSAGES["rolled_info"].format(
                    name=p.name, steps=steps, rolls=rolls_desc
                )
            )

            if cross > 0:
                reward = cross * 400  # Assuming 400 for passing Start
                results.append(
                    MESSAGES["passed_start"].format(name=p.name, reward=reward)
                )
                p.receive(reward)

            results.extend(self._resolve_field(p, new_pos, steps))

            # Jail (field or card) always ends the turn
            if p.in_jail:
                return results

            # Purchase decision pauses the turn before any extra roll
            if self.pending_purchase is not None:
                return results

            if not is_double:
                return results
            results.append(MESSAGES["extra_roll"].format(name=p.name))

    def _resolve_field(self, p, pos, steps):
        results = []
        field = self.board.fields[pos]
        results.append(
            MESSAGES["landed_on"].format(
                field_name=field["__name__"], field_type=field["type"]
            )
        )

        # Basic logic for different field types
        if field["type"] in ["city", "railway", "utility"]:
            owner = None
            for other_p in self.players:
                if field["id"] in [prop["id"] for prop in other_p.properties]:
                    owner = other_p
                    break

            if owner:
                if owner != p:
                    rent = 0
                    if field["type"] == "city":
                        # Basic rent (index 0)
                        rent = field.get("rent", [10])[0]
                        # Eurobiznes: double rent if owner has all cities of that country
                        if self._is_group_complete(owner, field.get("country")):
                            rent *= 2
                            results.append(MESSAGES["country_bonus"].format(rent=rent))

                    elif field["type"] == "railway":
                        # Railway rent: 50, 100, 200, 400 based on count
                        count = self._get_owned_in_group(owner, "railway")
                        # JSON provides [50, 100, 200, 400]
                        rent_list = field.get("rent", [50, 100, 200, 400])
                        rent = rent_list[min(count - 1, len(rent_list) - 1)]

                    elif field["type"] == "utility":
                        # Utility rent: Sum of dice * multiplier (8x or 20x)
                        count = self._get_owned_in_group(owner, "utility")
                        multipliers = field.get("rent_multiplier", [8, 20])
                        mult = multipliers[min(count - 1, len(multipliers) - 1)]
                        rent = steps * mult
                        results.append(
                            MESSAGES["utility_rent"].format(
                                steps=steps, mult=mult, rent=rent
                            )
                        )

                    results.append(
                        MESSAGES["paying_rent"].format(owner_name=owner.name, rent=rent)
                    )
                    p.pay(rent)
                    owner.receive(rent)
                else:
                    results.append(MESSAGES["own_property"])
            else:
                price = field.get("price", 0)
                results.append(MESSAGES["unowned_price"].format(price=price))
                if p.money >= price:
                    self.pending_purchase = {
                        "player_idx": self.players.index(p),
                        "field": pos,
                        "price": price,
                    }
                else:
                    results.append(
                        MESSAGES["cannot_afford"].format(
                            name=p.name, field_name=field["__name__"]
                        )
                    )

        elif field["type"] == "tax":
            cost = field.get("cost", 200)
            results.append(
                MESSAGES["tax_paid"].format(field_name=field["__name__"], cost=cost)
            )
            p.pay(cost)

        elif field["type"] == "chance":
            if field.get("color") == "red":
                msg = self.red_deck.draw(self, p)
            else:
                msg = self.blue_deck.draw(self, p)
            results.append(msg)

        elif field["type"] == "go_to_jail":
            results.append(MESSAGES["go_to_jail"].format(name=p.name))
            self._send_to_jail(p)

        return results

    def propose_trade(self, proposer_idx, target_idx, property_name, price, action):
        """Action is 'buy' or 'sell' from proposer's perspective."""
        if not isinstance(price, int) or price <= 0:
            return [MESSAGES["invalid_price"]]
        self.active_trade = {
            "proposer_idx": proposer_idx,
            "target_idx": target_idx,
            "property_name": property_name,
            "price": price,
            "action": action,
        }
        return [MESSAGES["trade_proposed"]]

    def respond_trade(self, responder_idx, response, new_price=None):
        if not self.active_trade:
            return [MESSAGES["no_active_trade"]]

        proposer_idx = self.active_trade["proposer_idx"]
        target_idx = self.active_trade["target_idx"]
        property_name = self.active_trade["property_name"]
        price = self.active_trade["price"]
        action = self.active_trade["action"]

        if responder_idx != target_idx:
            return [MESSAGES["waiting_for_other"]]

        proposer = self.players[proposer_idx]
        target = self.players[target_idx]

        if response == "reject":
            self.active_trade = None
            return [MESSAGES["trade_rejected"]]

        if response == "counter":
            if not isinstance(new_price, int) or new_price <= 0:
                return [MESSAGES["invalid_price"]]
            self.active_trade = {
                "proposer_idx": target_idx,
                "target_idx": proposer_idx,
                "property_name": property_name,
                "price": new_price,
                "action": "sell" if action == "buy" else "buy",
            }
            return [MESSAGES["counter_sent"]]

        if response == "accept":
            # Determine buyer and seller based on action from proposer perspective
            if action == "buy":
                buyer, seller = proposer, target
            else:
                buyer, seller = target, proposer

            if not isinstance(price, int) or price <= 0:
                self.active_trade = None
                return [MESSAGES["invalid_price"]]

            if buyer.money < price:
                self.active_trade = None
                return [MESSAGES["not_enough_money"]]

            # Find property
            prop_found = None
            for p in seller.properties:
                if p["__name__"] == property_name or p.get("name") == property_name:
                    prop_found = p
                    break

            if not prop_found:
                self.active_trade = None
                return [MESSAGES["seller_does_not_own"]]

            buyer.pay(price)
            seller.receive(price)

            # Recreate properties lists instead of .remove due to potential dict comparison issues
            seller.properties = [
                p
                for p in seller.properties
                if p.get("__name__") != property_name and p.get("name") != property_name
            ]
            buyer.properties.append(prop_found)

            self.active_trade = None
            return [
                MESSAGES["trade_success"].format(
                    buyer_name=buyer.name,
                    property_name=property_name,
                    seller_name=seller.name,
                    price=price,
                )
            ]

        return [MESSAGES["unknown_response"]]

    def decide_purchase(self, accept: bool) -> list[str]:
        if not self.pending_purchase:
            return [MESSAGES["no_pending_purchase"]]
        p = self.players[self.pending_purchase["player_idx"]]
        pos = self.pending_purchase["field"]
        price = self.pending_purchase["price"]
        field_name = self.board.fields[pos]["__name__"]

        if not accept:
            self.pending_purchase = None
            return [
                MESSAGES["declined_purchase"].format(name=p.name, field_name=field_name)
            ]

        # Guard: funds may have changed since landing
        if p.money < price:
            self.pending_purchase = None
            return [
                MESSAGES["declined_purchase"].format(
                    name=p.name, field_name=field_name
                ),
                MESSAGES["cannot_afford"].format(name=p.name, field_name=field_name),
            ]

        p.pay(price)
        p.properties.append(self.board.fields[pos])
        self.pending_purchase = None
        return [MESSAGES["bought_property"].format(name=p.name, field_name=field_name)]

    def get_state(self):
        winner = None
        if self.game_over:
            # Richest wins; ties resolved by alphabetically-first name
            winner = min(self.players, key=lambda p: (-p.money, p.name)).name
        return {
            "players": [
                {
                    "name": p.name,
                    "position": p.position,
                    "money": p.money,
                    "properties": [
                        {
                            "name": prop["__name__"],
                            "type": prop["type"],
                            "country": prop.get("country"),
                        }
                        for prop in p.properties
                    ],
                    "in_jail": p.in_jail,
                }
                for p in self.players
            ],
            "board": [
                {
                    "name": f["__name__"],
                    "type": f["type"],
                    "country": f.get("country"),
                }
                for f in self.board.fields
            ],
            "game_over": self.game_over,
            "winner": winner,
            "active_trade": self.active_trade,
            "pending_purchase": self.pending_purchase,
        }

    def save(self) -> dict:
        return {
            "version": SAVE_VERSION,
            "players": [
                {
                    "name": p.name,
                    "position": p.position,
                    "money": p.money,
                    "in_jail": p.in_jail,
                    "jail_turns": p.jail_turns,
                    "property_ids": [prop["id"] for prop in p.properties],
                }
                for p in self.players
            ],
            "deck_red": [card.text for card in self.red_deck.deck],
            "deck_blue": [card.text for card in self.blue_deck.deck],
            "active_trade": self.active_trade or None,
            "pending_purchase": self.pending_purchase or None,
            "game_over": bool(self.game_over),
        }

    def restore(self, data: dict) -> None:
        if data.get("version") != SAVE_VERSION:
            raise ValueError("Unsupported save version")

        field_by_id = {f["id"]: f for f in self.board.fields}
        for saved, live in zip(data.get("players", []), self.players):
            live.name = saved.get("name", live.name)
            live.position = saved.get("position", 0)
            live.money = saved.get("money", 0)
            live.in_jail = saved.get("in_jail", False)
            live.jail_turns = saved.get("jail_turns", 0)
            live.properties = [
                field_by_id[fid]
                for fid in saved.get("property_ids", [])
                if fid in field_by_id
            ]

        saved_red = data.get("deck_red", [])
        red = cards.get_default_red_deck()
        red_by_text = {c.text: c for c in red.cards}
        red.deck = [red_by_text[t] for t in saved_red if t in red_by_text]
        self.red_deck = red

        saved_blue = data.get("deck_blue", [])
        blue = cards.get_default_blue_deck()
        blue_by_text = {c.text: c for c in blue.cards}
        blue.deck = [blue_by_text[t] for t in saved_blue if t in blue_by_text]
        self.blue_deck = blue

        self.active_trade = data.get("active_trade")
        self.pending_purchase = data.get("pending_purchase")
        self.game_over = data.get("game_over", False)

    def run_cli(self):
        print("Starting ErloBiznes CLI!")
        turn_count = 0
        while not self.game_over and turn_count < 50:
            for p in self.players:
                messages = self.play_turn(p)
                for msg in messages:
                    print(msg)

                if p.money < 0:
                    print(f"{p.name} is bankrupt! Game over.")
                    self.game_over = True
                    break

            if self.game_over:
                break

            turn_count += 1
            input("\nPress Enter for next round...")


def main():
    my_game = ErloGame()
    my_game.run_cli()


if __name__ == "__main__":
    main()
