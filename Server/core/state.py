import os

from core.generation_settings import (
    DEFAULT_WORLD_PARAMS,
    calcular_percentuais_biomas,
)


def _ler_inteiro_ambiente(nome, padrao, minimo, maximo):
    valor = os.environ.get(nome)
    if valor is None:
        return padrao
    try:
        numero = int(valor)
    except ValueError:
        return padrao
    return numero if minimo <= numero <= maximo else padrao


class State:
    def __init__(self):
        # Config do mundo
        tamanho_mundo = _ler_inteiro_ambiente(
            "TILE_GAME_WORLD_SIZE",
            0,
            1,
            200,
        )
        self.altura_grid = tamanho_mundo or 90
        self.largura_grid = tamanho_mundo or 120
        self.world_seed = _ler_inteiro_ambiente(
            "TILE_GAME_WORLD_SEED",
            0,
            0,
            2_147_483_647,
        )
        self.world_params = dict(DEFAULT_WORLD_PARAMS)
        self.world_composition = calcular_percentuais_biomas(
            self.altura_grid * self.largura_grid,
            self.world_params,
        )
        self.world_revision = 0
        self.terrain_revision = 0

        # Mundo
        self.matriz = None
        self.matriz_dict = None

        # Lobby e autoridade. O token existe apenas no processo do anfitriao e
        # nunca faz parte dos snapshots enviados aos convidados.
        self.phase = "lobby"
        self.host_token = os.environ.get("TILE_GAME_HOST_TOKEN")
        self.room_code = os.environ.get("TILE_GAME_ROOM_CODE")
        self.host_player_id = None
        self.lobby_revision = 0
        self.world_generating = False
        self.world_error = None

        # Servidor / conexoes
        self.connections = []
        self.player_id_by_conn = {}
        self.player_id_by_session = {}
        self.player_session_by_id = {}
        self.active_conn_by_player_id = {}
        self.queues = {}
        self.sent_world_revision = {}

        # Players
        self.players = {}
        self.next_player_order = 1

        # Simulacao militar autoritativa. O cliente recebe apenas snapshots.
        self.troops = {}
        self.next_troop_id = 1
        self.recruitment_queues = {}
        self.next_recruitment_id = 1

        self.tempo_partida = 0
        self.partida_inicio_monotonic = None
        self.proximo_tick_monotonic = None
        self.tick_numero = 0


state = State()
