#!/usr/bin/env python
# -*- coding: utf-8 -*-
from erlobiznes.board import Board


class TestBoard:
    def test_board_loading(self):
        board = Board()
        assert len(board.fields) == 40
        assert board.fields[0]["__name__"] == "Start"
        assert board.fields[1]["country"] == "Grecja"
        assert board.fields[39]["__name__"] == "Wiedeń"
