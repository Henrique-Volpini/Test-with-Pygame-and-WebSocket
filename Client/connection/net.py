from core.state import state

from connection.handlers import receber as _receber_handler
from connection.transport import enviar as _enviar_transport
from connection.transport import iniciar as _iniciar_transport
from connection.transport import parar as _parar_transport


def iniciar(uri=None):
    _iniciar_transport(uri or state.ws_url, receber, _atualizar_status)


def enviar(dados):
    return _enviar_transport(dados)


def receber(data):
    return _receber_handler(data)


def parar():
    _parar_transport()


def _atualizar_status(conectado, erro):
    state.servidor_conectado = conectado
    if conectado:
        state.erro_conexao = None
        state.status_conexao = "Servidor conectado. Gerando o mundo..."
    elif state.iniciando_partida:
        state.status_conexao = "Aguardando o servidor local..."
