import core.recursos as recursos


class Tile:
    nome = ""
    produz = False

    custo_gold = 0
    custo_wood = 0
    custo_food = 0

    def __init__(self, current_player=None):
        self.current_player = current_player

    @classmethod
    def criar_custo(cls):
        return recursos.Recursos(
            gold=cls.custo_gold,
            wood=cls.custo_wood,
            food=cls.custo_food,
        )

    @classmethod
    def pagar(cls, recursos_player):
        custo = cls.criar_custo()
        if recursos_player.consigo_comprar(custo):
            recursos_player.comprei(custo)
            return True
        return False


class Grass(Tile):
    nome = "grass"
    custo_gold = 20


class LumberjackCabin(Tile):
    nome = "madeireiro"
    custo_gold = 80
    custo_wood = 120
    produz = True

    def __init__(self, current_player):
        super().__init__(current_player)
        self.contador_small_forest = 0


class Mountain(Tile):
    nome = "mountain"
    custo_gold = 80


class Mine(Tile):
    nome = "mine"
    custo_gold = 30
    custo_wood = 120
    custo_food = 60
    produz = True


class TownCenter(Tile):
    nome = "town_center"
    custo_gold = 200
    custo_wood = 150
    custo_food = 100


class City(Tile):
    nome = "city"
    custo_wood = 10


class GuardHouse(Tile):
    nome = "guard_house"
    custo_gold = 120
    custo_wood = 180
    custo_food = 80


class Water(Tile):
    nome = "water"
    custo_gold = 40


class Dock(Tile):
    nome = "dock"
    custo_gold = 100
    custo_wood = 220
    custo_food = 40


class SmallForest(Tile):
    nome = "small_forest"
    custo_gold = 30


class MediumForest(Tile):
    nome = "medium_forest"
    custo_gold = 50


class BigForest(Tile):
    nome = "big_forest"
    custo_gold = 80
