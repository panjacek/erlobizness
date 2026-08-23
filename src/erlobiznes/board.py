import json
import os


class Board:
    def __init__(self, board_file=None, language="pl"):
        if board_file is None:
            board_file = os.path.join(os.path.dirname(__file__), "board_layout.json")
            with open(board_file, "r") as f:
                self.fields = json.load(f)[language]
        else:
            self.fields = json.load(board_file)[language]
