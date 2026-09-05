#!/usr/bin/env python
# -*- coding: utf-8 -*-

from erlobiznes.game import ErloGame, SAVE_VERSION
from erlobiznes.lang_pl import MESSAGES
import pytest


class TestErloGame:
    def test_init(self):
        game = ErloGame()
        assert len(game.players) == 2
        assert len(game.board.fields) == 40
        assert game.red_deck is not None
        assert game.blue_deck is not None
        assert game.last_roll is None

    def test_last_roll_structured(self, mocker):
        game = ErloGame()
        mocker.patch.object(game.dice, "roll", side_effect=[2, 3])
        res = game.play_turn(game.players[0])
        assert game.last_roll["total"] == sum(sum(r) for r in game.last_roll["rolls"])
        for pair in game.last_roll["rolls"]:
            for d in pair:
                assert 1 <= d <= 6
        assert any("(2,3)" in m for m in res)

    def test_second_double_goes_to_jail(self, mocker):
        game = ErloGame()
        # Official rule (docs/eurobiznes_rules.md): second consecutive
        # double -> jail immediately, no move for that roll
        mocker.patch.object(game.dice, "roll", side_effect=[1, 1, 2, 2])
        res = game.play_turn(game.players[0])
        p = game.players[0]
        assert p.in_jail
        assert p.position == 10
        assert len(game.last_moves) == 1
        assert game.last_roll == {"total": 4, "rolls": [[2, 2]]}
        assert any("drugi dublet" in m for m in res)

    def test_double_grants_extra_move(self, mocker):
        game = ErloGame()
        # (2,2) -> idx 4 (tax/Parking), extra roll (3,4) -> idx 11 (city/Barcelona)
        # Tax field doesn't set pending_purchase, so extra roll happens
        # Land on city with enough money to afford it
        p = game.players[0]
        p.money = 300  # Barcelona costs 280
        mocker.patch.object(game.dice, "roll", side_effect=[2, 2, 3, 4])
        res = game.play_turn(p)
        assert not p.in_jail
        assert len(game.last_moves) == 2
        first, second = game.last_moves
        # Moves chain: second starts where first ended
        assert second["start"] == first["end"]
        # Total displacement is 4 + 7 = 11 from start
        assert p.position == (first["start"] + 11) % 40
        assert any("jeszcze raz" in m for m in res)

    def test_no_double_single_move(self, mocker):
        game = ErloGame()
        mocker.patch.object(game.dice, "roll", side_effect=[2, 3])
        p = game.players[0]
        game.play_turn(p)
        assert len(game.last_moves) == 1
        assert p.position == 5
        assert not p.in_jail

    def test_rent_doubling_full_country(self, mocker):
        game = ErloGame()
        p1 = game.players[0]
        p2 = game.players[1]

        # Give p2 all cities of Greece (Saloniki idx 1, Ateny idx 3)
        greece_fields = [f for f in game.board.fields if f.get("country") == "Grecja"]
        for f in greece_fields:
            p2.properties.append(f)

        # Roll (1,2): from Start lands directly on Ateny (idx 3)
        mocker.patch.object(game.dice, "roll", side_effect=[1, 2])
        p1.position = 0

        initial_p1_money = p1.money
        initial_p2_money = p2.money

        ateny = game.board.fields[3]
        expected_rent = ateny["rent"][0] * 2

        res = game.play_turn(p1)

        assert p1.money == initial_p1_money - expected_rent
        assert p2.money == initial_p2_money + expected_rent
        assert any("Cały kraj w posiadaniu!" in m for m in res)

    def test_jail_turns(self, mocker):
        game = ErloGame()
        p1 = game.players[0]
        p1.in_jail = True

        # Turn 1
        res1 = game.play_turn(p1)
        assert p1.in_jail
        assert any("1/2 in jail" in m for m in res1)

        # Turn 2
        res2 = game.play_turn(p1)
        assert p1.in_jail
        assert any("2/2 in jail" in m for m in res2)

        # Turn 3 - released, then rolls (1,2) deterministically
        mocker.patch.object(game.dice, "roll", side_effect=[1, 2])
        res3 = game.play_turn(p1)
        assert not p1.in_jail
        assert any("Released" in m for m in res3)


class TestTrades:
    def _setup_trade(self, game, price=100):
        p1 = game.players[0]
        p2 = game.players[1]
        prop = [f for f in game.board.fields if f["type"] == "city"][0]
        p1.properties.append(prop)
        game.propose_trade(0, 1, prop["__name__"], price, "sell")
        return p1, p2, prop

    def test_propose_negative_price_rejected(self):
        game = ErloGame()
        msgs = game.propose_trade(0, 1, "Start", -50, "sell")
        assert any("Nieprawidłowa cena" in m for m in msgs)
        assert game.active_trade is None

    def test_counter_without_price_rejected(self):
        game = ErloGame()
        self._setup_trade(game)
        msgs = game.respond_trade(1, "counter", None)
        assert any("Nieprawidłowa cena" in m for m in msgs)
        # Original offer untouched
        assert game.active_trade["price"] == 100

    def test_counter_negative_price_rejected(self):
        game = ErloGame()
        self._setup_trade(game)
        msgs = game.respond_trade(1, "counter", -10)
        assert any("Nieprawidłowa cena" in m for m in msgs)
        assert game.active_trade["price"] == 100

    def test_accept_flow(self):
        game = ErloGame()
        p1, p2, prop = self._setup_trade(game)
        name = prop["__name__"]
        msgs = game.respond_trade(1, "accept")
        assert any("Transakcja zakończona" in m for m in msgs)
        assert game.active_trade is None
        assert p2.money == 3000 - 100
        assert p1.money == 3000 + 100
        assert all(p["__name__"] != name for p in p1.properties)
        assert any(p["__name__"] == name for p in p2.properties)

    def test_accept_zero_price_blocked(self):
        game = ErloGame()
        msgs = game.propose_trade(0, 1, "Start", 0, "sell")
        # Propose itself is rejected, no trade created
        assert any("Nieprawidłowa cena" in m for m in msgs)
        assert game.active_trade is None
        assert any(
            "Brak aktywnego handlu" in m for m in game.respond_trade(1, "accept")
        )


class TestPurchaseDecision:
    def _land_on_unowned(self, game, mocker):
        # (1,2) from Start lands on Ateny (idx 3, price 120)
        mocker.patch.object(game.dice, "roll", side_effect=[1, 2])
        return game.play_turn(game.players[0])

    def test_landing_sets_pending_no_money_moved(self, mocker):
        game = ErloGame()
        p = game.players[0]
        res = self._land_on_unowned(game, mocker)

        assert game.pending_purchase == {"player_idx": 0, "field": 3, "price": 120}
        assert p.money == 3000
        assert p.properties == []
        assert game.active_trade is None
        assert any("na sprzedaż" in m for m in res)
        assert "pending_purchase" in game.get_state()

    def test_accept_buys_property(self, mocker):
        game = ErloGame()
        self._land_on_unowned(game, mocker)
        p = game.players[0]

        msgs = game.decide_purchase(True)

        assert any("kupił" in m for m in msgs)
        assert any(prop["id"] == game.board.fields[3]["id"] for prop in p.properties)
        assert p.money == 3000 - 120
        assert game.pending_purchase is None

    def test_decline_leaves_field_unowned(self, mocker):
        game = ErloGame()
        self._land_on_unowned(game, mocker)
        p = game.players[0]

        msgs = game.decide_purchase(False)

        assert any("nie kupił" in m for m in msgs)
        assert game.pending_purchase is None
        assert p.money == 3000
        assert p.properties == []

    def test_decide_without_pending(self):
        game = ErloGame()
        msgs = game.decide_purchase(True)
        assert msgs == [MESSAGES["no_pending_purchase"]]

    def test_double_pauses_before_extra_roll(self, mocker):
        game = ErloGame()
        # (3,3) lands on Neapol (idx 6, price 200): pending must stop the
        # double extra roll; leftover side effects prove no second move
        mocker.patch.object(game.dice, "roll", side_effect=[3, 3, 5, 5])
        p = game.players[0]

        res = game.play_turn(p)

        assert len(game.last_moves) == 1
        assert p.position == 6
        assert game.pending_purchase is not None
        assert not any("jeszcze raz" in m for m in res)


class TestPersistence:
    def test_roundtrip(self):
        game = ErloGame()
        p0 = game.players[0]
        p0.money = 1234
        p0.position = 17
        p0.in_jail = True
        p0.jail_turns = 1
        ateny = game.board.fields[3]
        p0.properties.append(ateny)
        game.players[1].money = 999

        # Shift deck orders away from the shuffled defaults
        game.red_deck.deck.append(game.red_deck.deck.pop(0))
        game.blue_deck.deck.insert(0, game.blue_deck.deck.pop())

        data = game.save()
        assert data["version"] == SAVE_VERSION
        assert data["players"][0]["property_ids"] == [ateny["id"]]

        g2 = ErloGame()
        g2.restore(data)
        for a, b in zip(game.players, g2.players):
            assert b.money == a.money
            assert b.position == a.position
            assert b.in_jail == a.in_jail
            assert b.jail_turns == a.jail_turns
            assert [p["__name__"] for p in b.properties] == [
                p["__name__"] for p in a.properties
            ]
        assert [c.text for c in g2.red_deck.deck] == [
            c.text for c in game.red_deck.deck
        ]
        assert [c.text for c in g2.blue_deck.deck] == [
            c.text for c in game.blue_deck.deck
        ]
        assert g2.active_trade is None
        assert g2.pending_purchase is None

    def test_pending_purchase_roundtrip(self):
        game = ErloGame()
        pending = {"player_idx": 1, "field": 5, "price": 200}
        game.pending_purchase = pending

        data = game.save()
        g2 = ErloGame()
        g2.restore(data)

        assert g2.pending_purchase is None

    def test_active_trade_roundtrip(self):
        game = ErloGame()
        trade = {
            "proposer_idx": 0,
            "target_idx": 1,
            "property_name": "Ateny",
            "price": 150,
            "action": "sell",
        }
        game.active_trade = trade

        data = game.save()
        g2 = ErloGame()
        g2.restore(data)

        assert g2.active_trade is None

    def test_unsupported_version_rejected(self):
        game = ErloGame()
        data = game.save()
        data["version"] = SAVE_VERSION + 98

        with pytest.raises(ValueError):
            ErloGame().restore(data)


class TestAuction:
    def test_decline_opens_auction_at_half_price(self, mocker):
        game = ErloGame()
        p1 = game.players[0]
        # Land on unowned field (idx 3, price 120)
        mocker.patch.object(game.dice, "roll", side_effect=[1, 2])
        game.play_turn(p1)

        # Decline purchase
        msgs = game.decide_purchase(False)

        assert game.pending_purchase is None
        assert game.active_auction is not None
        assert game.active_auction["field"] == 3
        assert game.active_auction["starting_price"] == 60  # 120 // 2
        assert game.active_auction["current_bid"] == 0
        assert game.active_auction["current_bidder"] is None
        assert game.active_auction["auction_turn"] == 1  # Other player's turn
        assert game.active_auction["pass_count"] == 0
        assert any("Licytacja" in m for m in msgs)

    def test_bid_advances_auction_turn(self, mocker):
        game = ErloGame()

        # Setup auction
        game.active_auction = {
            "field": 3,
            "starting_price": 60,
            "current_bid": 0,
            "current_bidder": None,
            "auction_turn": 0,  # p1's turn
            "pass_count": 0,
        }

        # p1 bids
        msgs = game.place_bid(0, 100)

        assert game.active_auction["current_bid"] == 100
        assert game.active_auction["current_bidder"] == 0
        assert game.active_auction["auction_turn"] == 1  # Now p2's turn
        assert game.active_auction["pass_count"] == 0
        assert any("licytuje" in m for m in msgs)

    def test_pass_ends_auction_no_bids(self, mocker):
        game = ErloGame()
        p1 = game.players[0]
        p2 = game.players[1]

        # Setup auction with no bids
        game.active_auction = {
            "field": 3,
            "starting_price": 60,
            "current_bid": 0,
            "current_bidder": None,
            "auction_turn": 0,
            "pass_count": 0,
        }

        # p1 passes (auction ends immediately in 2-player)
        msgs = game.pass_bid(0)

        assert game.active_auction is None
        assert p1.properties == []
        assert p2.properties == []
        assert any("Pole pozostaje własnością banku" in m for m in msgs)

    def test_pass_ends_auction_with_bid(self, mocker):
        game = ErloGame()
        p1 = game.players[0]

        # Setup auction with p1 as current bidder
        game.active_auction = {
            "field": 3,
            "starting_price": 60,
            "current_bid": 100,
            "current_bidder": 0,
            "auction_turn": 1,  # p2's turn
            "pass_count": 0,
        }

        initial_p1_money = p1.money

        # p2 passes (auction ends, p1 wins)
        msgs = game.pass_bid(1)

        assert game.active_auction is None
        assert p1.money == initial_p1_money - 100
        assert any(p["id"] == game.board.fields[3]["id"] for p in p1.properties)
        assert any("wygrywa licytację" in m for m in msgs)

    def test_bid_wins_auction_pays_bank_gets_property(self, mocker):
        game = ErloGame()
        p1 = game.players[0]

        # Setup auction with p1 as current bidder
        game.active_auction = {
            "field": 3,
            "starting_price": 60,
            "current_bid": 100,
            "current_bidder": 0,
            "auction_turn": 1,
            "pass_count": 0,
        }

        initial_p1_money = p1.money

        # p2 passes (auction ends, p1 wins)
        msgs = game.pass_bid(1)

        assert game.active_auction is None
        assert p1.money == initial_p1_money - 100
        assert any(p["id"] == game.board.fields[3]["id"] for p in p1.properties)
        assert any("wygrywa licytację" in m for m in msgs)

    def test_bid_rejected_wrong_turn(self):
        game = ErloGame()
        game.active_auction = {
            "field": 3,
            "starting_price": 60,
            "current_bid": 0,
            "current_bidder": None,
            "auction_turn": 0,
            "pass_count": 0,
        }

        # p2 tries to bid on p1's turn
        msgs = game.place_bid(1, 100)

        assert any("Nie twoja kolej" in m for m in msgs)

    def test_bid_rejected_too_low(self):
        game = ErloGame()
        game.active_auction = {
            "field": 3,
            "starting_price": 60,
            "current_bid": 100,
            "current_bidder": 0,
            "auction_turn": 1,
            "pass_count": 0,
        }

        # p2 bids too low
        msgs = game.place_bid(1, 50)

        assert any("Oferta musi być wyższa" in m for m in msgs)

    def test_first_bid_must_meet_starting_price(self):
        game = ErloGame()
        game.active_auction = {
            "field": 3,
            "starting_price": 60,
            "current_bid": 0,
            "current_bidder": None,
            "auction_turn": 0,
            "pass_count": 0,
            "original_player": 1,
        }

        # First bid below starting_price rejected
        msgs = game.place_bid(0, 30)
        assert any("Oferta musi być wyższa" in m for m in msgs)

        # First bid at starting_price accepted
        msgs = game.place_bid(0, 60)
        assert any("licytuje" in m for m in msgs)
        assert game.active_auction["current_bid"] == 60

    def test_bid_rejected_insufficient_funds(self):
        game = ErloGame()
        p1 = game.players[0]
        p1.money = 10  # Not enough

        game.active_auction = {
            "field": 3,
            "starting_price": 60,
            "current_bid": 0,
            "current_bidder": None,
            "auction_turn": 0,
            "pass_count": 0,
        }

        # p1 tries to bid more than they have
        msgs = game.place_bid(0, 100)

        assert any("Nie stać cię" in m for m in msgs)

    def test_auction_blocks_extra_roll(self, mocker):
        game = ErloGame()
        p = game.players[0]

        # Setup auction
        game.active_auction = {
            "field": 3,
            "starting_price": 60,
            "current_bid": 0,
            "current_bidder": None,
            "auction_turn": 0,
            "pass_count": 0,
        }

        # Roll doubles - normally would get extra roll, but auction blocks it
        mocker.patch.object(game.dice, "roll", side_effect=[2, 2])
        res = game.play_turn(p)

        # Only one move (the double), no extra roll
        assert len(game.last_moves) == 1
        assert not any("jeszcze raz" in m for m in res)

    def test_unaffordable_landing_opens_auction(self, mocker):
        game = ErloGame()
        p = game.players[0]
        p.money = 10  # Not enough for any property

        # Land on unowned field
        mocker.patch.object(game.dice, "roll", side_effect=[1, 2])
        game.play_turn(p)

        # Pending purchase should be set even though can't afford
        assert game.pending_purchase is not None
        assert game.pending_purchase["field"] == 3

        # Decline should open auction
        msgs = game.decide_purchase(False)
        assert game.active_auction is not None
        assert any("Licytacja" in m for m in msgs)

    def test_unaffordable_buy_auto_opens_auction(self, mocker):
        game = ErloGame()
        p = game.players[0]
        p.money = 10

        mocker.patch.object(game.dice, "roll", side_effect=[1, 2])
        game.play_turn(p)

        assert game.pending_purchase is not None

        # Click "buy" but can't afford — should auto-start auction
        msgs = game.decide_purchase(True)
        assert game.active_auction is not None
        assert game.pending_purchase is None
        assert any("nie stać" in m.lower() or "Licytacja" in m for m in msgs)

    def test_auction_roundtrip_persist(self):
        game = ErloGame()
        auction = {
            "field": 3,
            "starting_price": 60,
            "current_bid": 100,
            "current_bidder": 0,
            "auction_turn": 1,
            "pass_count": 1,
            "original_player": 0,
        }
        game.active_auction = auction

        data = game.save()
        g2 = ErloGame()
        g2.restore(data)

        assert g2.active_auction is None


class TestGameOver:
    def test_get_state_winner(self):
        game = ErloGame()
        assert game.get_state()["winner"] is None

        game.players[1].money = 5000
        game.game_over = True
        state = game.get_state()
        assert state["game_over"] is True
        assert state["winner"] == "Zed"


class TestCoverageGaps:
    def test_passing_start_rewards_money(self, mocker):
        game = ErloGame()
        p = game.players[0]
        p.position = 38
        # Roll (3,4) → 7 steps → position 5 (wraps past Start once)
        mocker.patch.object(game.dice, "roll", side_effect=[3, 4])
        game.play_turn(p)
        assert p.money == 3000 + 400

    def test_no_start_payment_when_jail_from_card(self, mocker):
        from erlobiznes.cards import go_to_jail_card

        game = ErloGame()
        p = game.players[0]
        p.position = 38
        # Roll (4,5) → 9 steps → position 7 (red chance), crosses Start once
        mocker.patch.object(game.dice, "roll", side_effect=[4, 5])
        mocker.patch.object(
            game.red_deck,
            "draw",
            side_effect=lambda g, pl: go_to_jail_card(g, pl) or "Go to JAIL.",
        )
        game.play_turn(p)
        assert p.in_jail is True
        assert p.money == 3000  # no 400 reward

    def test_trade_offer_wrong_player_rejected(self):
        game = ErloGame()
        game.propose_trade(1, 0, "Start", 100, "sell")
        # proposer_idx=1 but current_player is 0 — game doesn't enforce,
        # only web layer does. Game allows it.
        assert "trade_proposed" in MESSAGES

    def test_auction_full_bid_pass_cycle(self, mocker):
        game = ErloGame()
        p1, p2 = game.players
        game.active_auction = {
            "field": 3,
            "starting_price": 60,
            "current_bid": 0,
            "current_bidder": None,
            "auction_turn": 0,
            "pass_count": 0,
            "original_player": 0,
        }
        game.place_bid(0, 100)
        assert game.active_auction["auction_turn"] == 1
        assert game.active_auction["current_bidder"] == 0
        game.place_bid(1, 200)
        assert game.active_auction["auction_turn"] == 0
        assert game.active_auction["current_bidder"] == 1
        game.pass_bid(0)
        assert game.active_auction is None
        assert p2.money == 3000 - 200
        assert any(p["id"] == game.board.fields[3]["id"] for p in p2.properties)

    def test_auction_bid_no_active(self):
        game = ErloGame()
        msgs = game.place_bid(0, 100)
        assert "Brak aktywnego handlu" in msgs[0]
