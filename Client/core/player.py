import core.recursos as recursos

class Player:
    def __init__(self, player_id):
        self.id = player_id
        self.recursos = recursos.Recursos()