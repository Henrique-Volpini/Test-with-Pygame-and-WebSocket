import os


class State:
    def __init__(self):
        # Config do mundo
        tamanho_mundo = os.environ.get("TILE_GAME_WORLD_SIZE")
        self.altura_grid = int(tamanho_mundo) if tamanho_mundo else 90
        self.largura_grid = int(tamanho_mundo) if tamanho_mundo else 120

        # Mundo
        self.matriz = None
        self.matriz_dict = None

        # Servidor / conexoes
        self.connections = []
        self.player_id_by_conn = {}
        self.queues = {}

        # Players
        self.players = {}

        self.tempo_partida = 0


state = State()
