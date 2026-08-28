from threading import Lock

from connection import local_server, net
from core import session
from core.state import state
from core.window_settings import (
    WindowSettingsError,
    listar_resolucoes,
    validar_configuracao_janela,
)


class GameApi:
    """Fachada serializavel exposta ao JavaScript pelo pywebview."""

    def __init__(self):
        self._window = None
        self._actions = Lock()
        self._window_actions = Lock()
        self._shut_down = False

    def _bind_window(self, window):
        self._window = window

    def _shutdown(self):
        with self._window_actions:
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
                    "map_params": dict(state.lobby_map_params),
                    "map_composition": dict(state.lobby_map_composition),
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

    def configure_lobby(self, seed, world_size, map_params=None):
        with self._actions:
            if self._shut_down:
                return {"ok": False}
            return session.configurar_lobby(seed, world_size, map_params)

    def regenerate_lobby(self, world_size, map_params=None):
        with self._actions:
            if self._shut_down:
                return {"ok": False}
            return session.regenerar_lobby(world_size, map_params)

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

    @staticmethod
    def _window_settings_response(ok=True, error=None):
        with state.lock:
            response = {
                "ok": ok,
                "width": state.window_width,
                "height": state.window_height,
                "fullscreen": state.tela_cheia_ativa,
                "resolutions": listar_resolucoes(),
            }
        if error:
            response["error"] = str(error)
        return response

    def get_window_settings(self):
        with self._window_actions:
            return self._window_settings_response()

    @staticmethod
    def _rollback_window(
        window,
        native_fullscreen,
        previous_fullscreen,
        previous_geometry,
    ):
        """Tenta devolver a janela ao estado anterior sem mascarar o erro original."""
        try:
            if native_fullscreen:
                window.toggle_fullscreen()
                native_fullscreen = False

            if previous_geometry is not None:
                width, height, x, y = previous_geometry
                window.restore()
                window.resize(width, height)
                window.move(x, y)

            if previous_fullscreen and not native_fullscreen:
                window.toggle_fullscreen()
            return True
        except Exception:
            return False

    def apply_window_settings(
        self,
        width,
        height,
        fullscreen,
        display_bounds=None,
    ):
        try:
            width, height, fullscreen, bounds = validar_configuracao_janela(
                width,
                height,
                fullscreen,
                display_bounds,
            )
        except WindowSettingsError as error:
            return self._window_settings_response(False, error)

        with self._window_actions:
            window = self._window
            if window is None or self._shut_down:
                return self._window_settings_response(
                    False,
                    "A janela do jogo não está disponível.",
                )

            with state.lock:
                previous_fullscreen = state.tela_cheia_ativa

            native_fullscreen = previous_fullscreen
            previous_geometry = None
            try:
                if native_fullscreen:
                    window.toggle_fullscreen()
                    native_fullscreen = False

                previous_geometry = (
                    window.width,
                    window.height,
                    window.x,
                    window.y,
                )
                window.restore()
                window.resize(width, height)

                if bounds is None:
                    previous_width, previous_height, previous_x, previous_y = (
                        previous_geometry
                    )
                    target_x = previous_x + (previous_width - width) // 2
                    target_y = previous_y + (previous_height - height) // 2
                else:
                    target_x, target_y = bounds.centered_position(width, height)
                window.move(target_x, target_y)

                if fullscreen:
                    window.toggle_fullscreen()
                    native_fullscreen = True

                with state.lock:
                    state.window_width = width
                    state.window_height = height
                    state.tela_cheia_ativa = fullscreen
            except Exception:
                recovered = self._rollback_window(
                    window,
                    native_fullscreen,
                    previous_fullscreen,
                    previous_geometry,
                )
                message = "Não foi possível aplicar as configurações da janela."
                if not recovered:
                    message += " A restauração da janela também falhou."
                return self._window_settings_response(False, message)

            return self._window_settings_response()

    def toggle_fullscreen(self, display_bounds=None):
        with self._window_actions:
            window = self._window
            if window is None or self._shut_down:
                return self._window_settings_response(
                    False,
                    "A janela do jogo não está disponível.",
                )

            with state.lock:
                previous_fullscreen = state.tela_cheia_ativa
                width = state.window_width
                height = state.window_height

            if previous_fullscreen:
                try:
                    window.toggle_fullscreen()
                except Exception:
                    return self._window_settings_response(
                        False,
                        "Não foi possível alternar o modo de tela cheia.",
                    )

                with state.lock:
                    state.tela_cheia_ativa = False
                return self._window_settings_response()

            try:
                width, height, _, bounds = validar_configuracao_janela(
                    width,
                    height,
                    True,
                    display_bounds,
                )
            except WindowSettingsError as error:
                return self._window_settings_response(False, error)

            previous_geometry = None
            native_fullscreen = False
            try:
                previous_geometry = (
                    window.width,
                    window.height,
                    window.x,
                    window.y,
                )
                window.restore()
                window.resize(width, height)

                if bounds is None:
                    previous_width, previous_height, previous_x, previous_y = (
                        previous_geometry
                    )
                    target_x = previous_x + (previous_width - width) // 2
                    target_y = previous_y + (previous_height - height) // 2
                else:
                    target_x, target_y = bounds.centered_position(width, height)
                window.move(target_x, target_y)
                window.toggle_fullscreen()
                native_fullscreen = True

                with state.lock:
                    state.window_width = width
                    state.window_height = height
                    state.tela_cheia_ativa = True
            except Exception:
                recovered = self._rollback_window(
                    window,
                    native_fullscreen,
                    previous_fullscreen,
                    previous_geometry,
                )
                message = "Não foi possível alternar o modo de tela cheia."
                if not recovered:
                    message += " A restauração da janela também falhou."
                return self._window_settings_response(False, message)

            return self._window_settings_response()

    def close_window(self):
        with self._window_actions:
            with self._actions:
                window = self._window
                if window is None or self._shut_down:
                    return {"ok": False}

                window.destroy()
        return {"ok": True}
