# Aqui fica as principais do jogo, antes tinha muitos globais espalhados e estava dando muito problema
# Isso vai facilitar eu criar saves dps tbm

class GameState:
    def __init__(self):
        # Em que menu esta
        self.estado_jogo = "menu_main"

        # Matriz do jogo
        self.matriz = []
        self.matriz_pronta = False
        self.altura_grid = 0
        self.largura_grid = 0

        # Feito pra algumas validacoes
        self.player_id_criado = False
        self.partida_criada = False

        # Armazenar player id, partida atual e jogador atual
        self.player_id = None
        self.partida_atual = None
        self.current_player = None

        # para selecao correta de tiles
        self.selected_tile = None
        self.pre_selected_tile = None
        self.mouse_pos = (0, 0)

        # camera
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.camera_speed = 10.0

        self.zoom = 1.0
        self.zoom_min = 1.0
        self.zoom_max = 2.5
        self.zoom_step = 0.1

        self.zoom_cache = {}

        # Os menus
        self.menu_build = None
        self.menu_recursos = None
        self.menu_main = None

        # Configurações do jogo no geral
        self.tela_cheia_ativa = False
        self.atualizar_modo_video = False
        self.tile_size = 32
        self.fps = 60
        self.largura_tela = 1280
        self.altura_tela = 960

        # Configurações de rede
        self.ws_url = "ws://127.0.0.1:8765/ws"
        self.iniciando_partida = False
        self.servidor_conectado = False
        self.status_conexao = ""
        self.erro_conexao = None



state = GameState()
