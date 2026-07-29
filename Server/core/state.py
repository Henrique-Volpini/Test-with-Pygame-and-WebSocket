class State:
    def __init__(self):
        # Config do mundo
        self.altura_grid = 90
        self.largura_grid = 120

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
