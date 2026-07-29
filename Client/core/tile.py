import pygame

import core.recursos as recursos

import ui.assets_paths as paths

class Tile:
    image = None
    produz = False

    ##lembrar q se adicionar um recurso novo tem q sair colocando nos tiles e aqui krl
    custo_gold = 0
    custo_wood = 0
    custo_food = 0

    def __init__(self):
        self.current_player = None
    
    ##Isso aqui em baixo está gastando o recurso do player ativo com os recursos
    ##Se adicionar outro recurso tem q mexer aqui tbm em
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
    

##Daqui pra baixo é os filhos do pai Tile
class Grass(Tile):
    custo_gold = 20

    def __init__(self, current_player=None):
        super().__init__()
        self.current_player = current_player

    @classmethod
    def load_assets(cls):
        cls.image = pygame.image.load(paths.GRASS).convert_alpha()

class LumberjackCabin(Tile):
    custo_gold = 80
    custo_wood = 120
    custo_food = 0

    produz = True

    def __init__(self, current_player):
        super().__init__()
        self.current_player = current_player
        self.contador_small_forest = 0

    @classmethod
    def load_assets(cls):
        cls.image = pygame.image.load(paths.LUMBERJACK_CABIN).convert_alpha()

class Mountain(Tile):
    custo_gold = 80
    custo_wood = 0
    custo_food = 0

    def __init__(self, current_player):
        super().__init__()
        self.current_player = current_player

    @classmethod
    def load_assets(cls):
        cls.image = pygame.image.load(paths.MOUNTAIN).convert_alpha()

class Mine(Tile):
    custo_gold = 30
    custo_wood = 120
    custo_food = 60

    produz = True

    def __init__(self, current_player):
        super().__init__()
        self.current_player = current_player

    @classmethod
    def load_assets(cls):
        cls.image = pygame.image.load(paths.MINE).convert_alpha()
    
class TownCenter(Tile):
    custo_gold = 200
    custo_wood = 150
    custo_food = 100


    def __init__(self, current_player):
        super().__init__()
        self.current_player = current_player

    @classmethod
    def load_assets(cls):
        cls.image = pygame.image.load(paths.TOWN_CENTER).convert_alpha()

class City(Tile):
    custo_gold = 0
    custo_wood = 10
    custo_food = 0

    def __init__(self, current_player):
        super().__init__()
        self.current_player = current_player

    @classmethod
    def load_assets(cls):
        cls.image = pygame.image.load(paths.CITY).convert_alpha()

class Water(Tile):
    custo_gold = 0
    custo_wood = 0
    custo_food = 0

    def __init__(self, current_player=None):
        super().__init__()
        self.current_player = current_player

    @classmethod
    def load_assets(cls):
        cls.image = pygame.image.load(paths.WATER).convert_alpha()

class SmallForest(Tile):
    custo_gold = 30
    custo_wood = 0
    custo_food = 0

    def __init__(self, current_player):
        super().__init__()
        self.current_player = current_player

    @classmethod
    def load_assets(cls):
        cls.image = pygame.image.load(paths.SMALL_FOREST).convert_alpha()

class MediumForest(Tile):
    custo_gold = 50
    custo_wood = 0
    custo_food = 0

    def __init__(self, current_player):
        super().__init__()
        self.current_player = current_player

    @classmethod
    def load_assets(cls):
        cls.image = pygame.image.load(paths.MEDIUM_FOREST).convert_alpha()
    
class BigForest(Tile):
    custo_gold = 80
    custo_wood = 0
    custo_food = 0

    def __init__(self, current_player):
        super().__init__()
        self.current_player = current_player

    @classmethod
    def load_assets(cls):
        cls.image = pygame.image.load(paths.BIG_FOREST).convert_alpha()
