class Player:
    def __init__(self, name):
        self.name = name
        self.position = 0
        self.money = 3000
        self.properties = []
        self.mortgaged = set()
        self.in_jail = False
        self.jail_turns = 0
        self.get_out_of_jail_free = 0

    def is_mortgaged(self, prop_id):
        return prop_id in self.mortgaged

    def mortgage_property(self, prop_id):
        self.mortgaged.add(prop_id)

    def unmortgage_property(self, prop_id):
        self.mortgaged.discard(prop_id)

    def attempt_jail_escape(self):
        self.jail_turns += 1
        if self.jail_turns >= 3:
            self.in_jail = False
            self.jail_turns = 0
            return True, "Released after skipping 2 turns"
        return False, f"Turn {self.jail_turns}/2 in jail"

    def walk(self, steps, board_size):
        """make a walk over a board
        Args:
            steps: number of steps to move
            board_size: size of the board
        Returns:
            number of times crossed 0 point,
            position on board
        """
        if self.in_jail:
            return 0, self.position

        new_position = self.position + steps
        cross = new_position // board_size
        self.position = new_position % board_size

        return cross, self.position

    def pay(self, amount):
        """Deduct money unconditionally. May go negative; callers detect
        bankruptcy via money < 0 after the turn."""
        self.money -= amount

    def receive(self, amount):
        self.money += amount
