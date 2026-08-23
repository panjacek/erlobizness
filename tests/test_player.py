#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pytest
from erlobiznes.player import Player


class TestPlayer:
    def test_init(self):
        with pytest.raises(TypeError):
            erlo_player = Player()

        erlo_player = Player("PLAYER3")
        assert erlo_player.name == "PLAYER3"
        assert erlo_player.position == 0
        assert erlo_player.money == 3000
        assert erlo_player.properties == []
        assert erlo_player.in_jail is False
        assert erlo_player.jail_turns == 0
        assert erlo_player.get_out_of_jail_free == 0

    @pytest.mark.parametrize(
        "start_pos, steps, board_size, expected_cross, expected_pos",
        [
            (0, 5, 40, 0, 5),  # Normal move from start
            (38, 3, 40, 1, 1),  # Cross start
            (39, 1, 40, 1, 0),  # Land exactly on start (0-indexed)
            (10, 30, 40, 1, 0),  # Cross start and land on start
            (5, 40, 40, 1, 5),  # Full circle, back to original position
            (5, 45, 40, 1, 10),  # One full circle and move
            (35, 10, 40, 1, 5),  # Cross start and move
        ],
    )
    def test_walk_movement(
        self, start_pos, steps, board_size, expected_cross, expected_pos
    ):
        player = Player("TestPlayer")
        player.position = start_pos
        cross, new_pos = player.walk(steps, board_size)
        assert cross == expected_cross
        assert new_pos == expected_pos

    def test_walk_in_jail(self):
        player = Player("TestPlayer")
        player.position = 10
        player.in_jail = True
        cross, new_pos = player.walk(5, 40)
        assert cross == 0
        assert new_pos == 10  # Position should not change if in jail

    def test_pay_money(self):
        player = Player("TestPlayer")
        initial_money = player.money
        player.pay(500)
        assert player.money == initial_money - 500

    def test_pay_can_go_negative(self):
        # Bankruptcy is detected by money < 0, pay must always deduct
        player = Player("TestPlayer")
        player.pay(5000)
        assert player.money == 3000 - 5000
        assert player.money < 0

    def test_jail_escape(self):
        player = Player("TestPlayer")
        player.in_jail = True

        # Turn 1
        escaped, msg = player.attempt_jail_escape()
        assert not escaped
        assert player.in_jail
        assert player.jail_turns == 1

        # Turn 2
        escaped, msg = player.attempt_jail_escape()
        assert not escaped
        assert player.in_jail
        assert player.jail_turns == 2

        # Turn 3 - Should escape (Eurobiznes rule: skip 2 turns)
        escaped, msg = player.attempt_jail_escape()
        assert escaped
        assert not player.in_jail
        assert player.jail_turns == 0
        assert "Released" in msg

    def test_receive_money(self):

        player = Player("TestPlayer")
        initial_money = player.money
        player.receive(200)
        assert player.money == initial_money + 200
        player.receive(1000)
        assert player.money == initial_money + 1200
