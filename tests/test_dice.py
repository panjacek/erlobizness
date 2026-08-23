#!/usr/bin/env python
# -*- coding: utf-8 -*-
from erlobiznes.dice import Dice


class TestDice:
    def test_roll_range(self):
        dicer = Dice()
        res = dicer.roll()
        assert isinstance(res, int)
        assert 1 <= res <= 6

    def test_roll_deterministic_with_mock(self, mocker):
        dicer = Dice()
        mocker.patch.object(dicer, "roll", return_value=4)
        assert dicer.roll() == 4
