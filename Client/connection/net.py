import secrets

from core.state import state

from connection.handlers import receber as _receber_handler
from connection.transport import enviar as _enviar_transport
from connection.transport import iniciar as _iniciar_transport
from connection.transport import parar as _parar_transport


PERMANENT_CONNECTION_ERRORS = {
    "game_already_started": "A partida já começou e não aceita novos jogadores.",
    "host_already_connected": "O anfitrião já está conectado por outra sessão.",
    "invalid_host_session": "A credencial do anfitrião não é válida.",
    "player_session_conflict": "Esta sessão pertence a outro jogador.",
}


def iniciar(uri=None, host_token=None):
    headers = {"X-Tile-Game-Player": secrets.token_urlsafe(32)}
    if host_token:
        headers["X-Tile-Game-Host"] = host_token
    _iniciar_transport(
        uri or state.ws_url,
        receber,
        _atualizar_status,
        headers=headers,
    )


def enviar(dados):
    return _enviar_transport(dados)


def receber(data):
    return _receber_handler(data)


def parar():
    _parar_transport()


def _atualizar_status(conectado, erro):
    with state.lock:
        state.servidor_conectado = conectado
        if conectado:
            state.erro_conexao = None
            state.status_conexao = "Servidor conectado. Sincronizando a sala..."
        else:
            permanent_message = next(
                (
                    message
                    for code, message in PERMANENT_CONNECTION_ERRORS.items()
                    if code in str(erro or "")
                ),
                None,
            )
            if permanent_message is not None:
                state.iniciando_partida = False
                state.erro_conexao = permanent_message
                state.status_conexao = permanent_message
                return

            state.erro_conexao = erro
            if state.iniciando_partida and state.session_mode == "host":
                state.status_conexao = "Aguardando o servidor local..."
            elif state.iniciando_partida:
                state.status_conexao = "Tentando alcançar a sala..."
            else:
                state.status_conexao = "Servidor desconectado."
                if state.estado_jogo == "lobby":
                    state.lobby_status = "Servidor desconectado."
                    state.lobby_error = erro or "A conexão com a sala foi perdida."
                    state.lobby_generating = False
                    state.lobby_revision += 1
