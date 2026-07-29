import core.recursos as recursos

class Tile:
    image = None
    produz = False

    ##lembrar q se adicionar um recurso novo tem q sair colocando nos tiles e aqui krl
    custo_gold = 0
    custo_wood = 0
    custo_food = 0

    def __init__(self):
        self.current_player = None

    def producao(self):
        return None
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

class LumberjackCabin(Tile):
    custo_gold = 80
    custo_wood = 120
    custo_food = 0

    produz = True

    def __init__(self, current_player):
        super().__init__()
        self.current_player = current_player
        self.contador_small_forest = 0


    def producao(self):
        return recursos.Recursos(gold=0, wood=self.contador_small_forest, food=0)
    
    def count_forest(self, matriz, selected_tile, raio=2):

        x0, y0 = selected_tile
        max_y = len(matriz)
        max_x = len(matriz[0])

        contador = 0
        for y in range(max(0, y0 - raio), min(max_y, y0 + raio + 1)):
            for x in range(max(0, x0 - raio), min(max_x, x0 + raio + 1)):
                if isinstance(matriz[y][x], SmallForest):
                    contador += 1
                elif isinstance(matriz[y][x], MediumForest):
                    contador += 2
                elif isinstance(matriz[y][x], BigForest):
                    contador += 3
        self.contador_small_forest = contador

class Mountain(Tile):
    custo_gold = 80
    custo_wood = 0
    custo_food = 0

    def __init__(self, current_player):
        super().__init__()
        self.current_player = current_player

class Mine(Tile):
    custo_gold = 30
    custo_wood = 120
    custo_food = 60

    produz = True

    def __init__(self, current_player):
        super().__init__()
        self.current_player = current_player

    def producao(self):
        return recursos.Recursos(gold=10, wood=0, food=0)
    
class TownCenter(Tile):
    custo_gold = 200
    custo_wood = 150
    custo_food = 100

    def __init__(self, current_player):
        super().__init__()
        self.current_player = current_player

class City(Tile):
    custo_gold = 0
    custo_wood = 10
    custo_food = 0

    def __init__(self, current_player):
        super().__init__()
        self.current_player = current_player

class Water(Tile):
    custo_gold = 0
    custo_wood = 0
    custo_food = 0

    def __init__(self, current_player):
        super().__init__()
        self.current_player = current_player

class SmallForest(Tile):
    custo_gold = 30
    custo_wood = 0
    custo_food = 0

    def __init__(self, current_player):
        super().__init__()
        self.current_player = current_player

    def atualizar_lumberjackCabin(self, matriz, selected_tile, raio=2):

        x0, y0 = selected_tile
        max_y = len(matriz)
        max_x = len(matriz[0])

        for y in range(max(0, y0 - raio), min(max_y, y0 + raio + 1)):
            for x in range(max(0, x0 - raio), min(max_x, x0 + raio + 1)):
                if isinstance(matriz[y][x], LumberjackCabin):
                    matriz[y][x].count_forest(matriz, (x,y))

class MediumForest(Tile):
    custo_gold = 50
    custo_wood = 0
    custo_food = 0

    def __init__(self, current_player):
        super().__init__()
        self.current_player = current_player

    def atualizar_lumberjackCabin(self, matriz, selected_tile, raio=2):

        x0, y0 = selected_tile
        max_y = len(matriz)
        max_x = len(matriz[0])

        for y in range(max(0, y0 - raio), min(max_y, y0 + raio + 1)):
            for x in range(max(0, x0 - raio), min(max_x, x0 + raio + 1)):
                if isinstance(matriz[y][x], LumberjackCabin):
                    matriz[y][x].count_forest(matriz, (x,y))

class BigForest(Tile):
    custo_gold = 80
    custo_wood = 0
    custo_food = 0

    def __init__(self, current_player):
        super().__init__()
        self.current_player = current_player


    def atualizar_lumberjackCabin(self, matriz, selected_tile, raio=2):

        x0, y0 = selected_tile
        max_y = len(matriz)
        max_x = len(matriz[0])

        for y in range(max(0, y0 - raio), min(max_y, y0 + raio + 1)):
            for x in range(max(0, x0 - raio), min(max_x, x0 + raio + 1)):
                if isinstance(matriz[y][x], LumberjackCabin):
                    matriz[y][x].count_forest(matriz, (x,y))