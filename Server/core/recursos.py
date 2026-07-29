class Recursos:
    def __init__(self, gold=500, wood=500, food=500):
        self.gold = gold
        self.wood = wood
        self.food = food

    def consigo_comprar(self, cost):
        return (self.gold >= cost.gold and self.wood >= cost.wood and self.food >= cost.food)

    def comprei(self, cost):
        self.gold -= cost.gold
        self.wood -= cost.wood
        self.food -= cost.food

    def to_dict(self):
        return {
            "gold": self.gold,
            "wood": self.wood,
            "food": self.food,
        }
