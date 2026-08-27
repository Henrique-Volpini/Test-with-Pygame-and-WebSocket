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

    def get_snapshot(self, known_world_revision=-1):
        if isinstance(known_world_revision, bool) or not isinstance(
            known_world_revision, (int, float)
        ):
            known_world_revision = -1
        else:
            try:
                known_world_revision = int(known_world_revision)
            except (OverflowError, ValueError):
                known_world_revision = -1

        with state.lock:
            em_partida = state.estado_jogo == "partida"
            world_revision = state.world_revision
            matrix = None
            if em_partida and known_world_revision != world_revision:
                matrix = state.matriz_render

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

            return {
                "screen": "game" if em_partida else "menu",
                # Nao avance o cursor do frontend antes de a sessao estar
                # pronta; matriz e transicao sao observadas no mesmo snapshot.
                "world_revision": (
                    world_revision if em_partida else known_world_revision
                ),
                "matrix": matrix,
                "width": state.largura_grid,
                "height": state.altura_grid,
                "resources": resources,
            }

    def host_game(self, world_size):
        with self._actions:
            if self._shut_down:
                return {"ok": False}
            return session.hostear(world_size)

    def connect_game(self, code):
        with self._actions:
            if self._shut_down:
                return {"ok": False}
            return session.conectar(code)

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
