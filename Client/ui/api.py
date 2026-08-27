from threading import Lock

from connection import local_server, net
from core import session
from core.state import state


class GameApi:
    """Fachada serializavel exposta ao JavaScript pelo pywebview."""

    def __init__(self):
        self._window = None
        self._actions = Lock()
        self._shut_down = False

    def _bind_window(self, window):
        self._window = window

    def _shutdown(self):
        with self._actions:
            if self._shut_down:
                return
            net.parar()
            local_server.encerrar()
            self._shut_down = True

    @staticmethod
    def _normalize_revision(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return -1
        try:
            return int(value)
        except (OverflowError, ValueError):
            return -1

    def get_snapshot(
        self,
        known_world_revision=-1,
        known_lobby_world_revision=-1,
    ):
        known_world_revision = self._normalize_revision(known_world_revision)
        known_lobby_world_revision = self._normalize_revision(
            known_lobby_world_revision
        )

        with state.lock:
            em_partida = state.estado_jogo == "partida"
            em_lobby = state.estado_jogo == "lobby"
            world_revision = state.world_revision
            matrix = None
            if em_partida and known_world_revision != world_revision:
                matrix = state.matriz_render

            lobby = None
            if em_lobby:
                lobby_matrix = None
                if known_lobby_world_revision != state.lobby_world_revision:
                    lobby_matrix = state.matriz_render
                lobby = {
                    "revision": state.lobby_revision,
                    "world_revision": state.lobby_world_revision,
                    "matrix": lobby_matrix,
                    "width": state.largura_grid,
                    "height": state.altura_grid,
                    "seed": state.lobby_seed,
                    "size": state.lobby_size,
                    "players": [dict(item) for item in state.lobby_players],
                    "player_count": len(state.lobby_players),
                    "is_host": state.lobby_is_host,
                    "code": state.lobby_code,
                    "generating": state.lobby_generating,
                    "status": state.lobby_status,
                    "error": state.lobby_error,
                }

            if state.current_player is not None:
                recursos = state.current_player.recursos
                resources = {
                    "gold": recursos.gold,
                    "wood": recursos.wood,
                    "food": recursos.food,
                }
            elif state.recursos_pendentes is not None:
                resources = dict(state.recursos_pendentes)
            else:
                resources = {"gold": 500, "wood": 500, "food": 500}

            if em_partida:
                screen = "game"
            elif em_lobby:
                screen = "lobby"
            elif state.estado_jogo == "menu_host":
                screen = "host"
            elif state.estado_jogo == "menu_connect":
                screen = "connect"
            else:
                screen = "main"

            return {
                "screen": screen,
                "session_mode": state.session_mode,
                # Nao avance o cursor do frontend antes de a sessao estar
                # pronta; matriz e transicao sao observadas no mesmo snapshot.
                "world_revision": (
                    world_revision if em_partida else known_world_revision
                ),
                "matrix": matrix,
                "width": state.largura_grid,
                "height": state.altura_grid,
                "resources": resources,
                "lobby": lobby,
                "connection": {
                    "connected": state.servidor_conectado,
                    "status": state.status_conexao,
                    "error": state.erro_conexao,
                },
            }

    def host_game(self, world_size=90, seed=None):
        with self._actions:
            if self._shut_down:
                return {"ok": False}
            return session.hostear(world_size, seed)

    def connect_game(self, code):
        with self._actions:
            if self._shut_down:
                return {"ok": False}
            return session.conectar(code)

    def configure_lobby(self, seed, world_size):
        with self._actions:
            if self._shut_down:
                return {"ok": False}
            return session.configurar_lobby(seed, world_size)

    def regenerate_lobby(self, world_size):
        with self._actions:
            if self._shut_down:
                return {"ok": False}
            return session.regenerar_lobby(world_size)

    def start_lobby(self):
        with self._actions:
            if self._shut_down:
                return {"ok": False}
            return session.iniciar_lobby()

    def leave_lobby(self):
        with self._actions:
            if self._shut_down:
                return {"ok": False}
            return session.sair_lobby()

    def build_tile(self, x, y, tile_name):
        with self._actions:
            if self._shut_down:
                return {"ok": False}
            return session.construir(x, y, tile_name)

    def toggle_fullscreen(self):
        window = self._window
        if window is None:
            return {"ok": False}

        window.toggle_fullscreen()
        with state.lock:
            state.tela_cheia_ativa = not state.tela_cheia_ativa
        return {"ok": True}

    def close_window(self):
        with self._actions:
            window = self._window
            if window is None or self._shut_down:
                return {"ok": False}

            window.destroy()
        return {"ok": True}
