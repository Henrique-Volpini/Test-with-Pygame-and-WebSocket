from threading import RLock


class GameState:
    """Estado compartilhado entre a rede e a ponte da interface web."""

    def __init__(self):
        self.lock = RLock()

        # Sessao atual
        self.estado_jogo = "menu_main"
        self.player_id = None
        self.player_id_criado = False
        self.current_player = None
        self.recursos_pendentes = None
        self.partida_criada = False

        # Mundo recebido do servidor. A matriz de renderizacao contem somente
        # nomes serializaveis; a matriz de objetos preserva o modelo do cliente.
        self.matriz = []
        self.matriz_render = []
        self.matriz_wire = None
        self.matriz_pronta = False
        self.altura_grid = 0
        self.largura_grid = 0
        self.world_revision = 0

        # Janela
        self.tela_cheia_ativa = False

        # Rede
        self.ws_url = "ws://127.0.0.1:8765/ws"
        self.session_mode = None
        self.iniciando_partida = False
        self.servidor_conectado = False
        self.status_conexao = ""
        self.erro_conexao = None

    def resetar_sessao(self, ws_url, status, mode):
        """Prepara uma nova conexao sem alterar o estado da janela."""
        with self.lock:
            self.estado_jogo = "menu_main"
            self.player_id = None
            self.player_id_criado = False
            self.current_player = None
            self.recursos_pendentes = None
            self.partida_criada = False

            self.matriz = []
            self.matriz_render = []
            self.matriz_wire = None
            self.matriz_pronta = False
            self.altura_grid = 0
            self.largura_grid = 0
            self.world_revision += 1

            self.servidor_conectado = False
            self.iniciando_partida = True
            self.erro_conexao = None
            self.status_conexao = status
            self.ws_url = ws_url
            self.session_mode = mode


state = GameState()
