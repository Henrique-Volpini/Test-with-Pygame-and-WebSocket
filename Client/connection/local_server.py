import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys

from connection import net
from core.state import state


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = PROJECT_ROOT / "Server"
SERVER_LOG = PROJECT_ROOT / "server.log"

_process = None
_log_handle = None
LOCAL_WS_URL = "ws://127.0.0.1:8765/ws"


def porta_servidor_em_uso():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        return sock.connect_ex(("127.0.0.1", 8765)) == 0
    finally:
        sock.close()


def iniciar(tamanho_mundo=None):
    global _process, _log_handle

    if state.iniciando_partida:
        return True

    dependencias = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "websockets": "websockets",
        "perlin-noise": "perlin_noise",
    }
    ausentes = [
        pacote
        for pacote, modulo in dependencias.items()
        if importlib.util.find_spec(modulo) is None
    ]
    if ausentes:
        state.erro_conexao = "Dependencias ausentes: " + ", ".join(ausentes)
        print(state.erro_conexao)
        return False

    if porta_servidor_em_uso():
        state.erro_conexao = "A porta 8765 ja esta sendo usada por outro servidor. Feche o processo antigo."
        print(state.erro_conexao)
        return False

    state.player_id = None
    state.player_id_criado = False
    state.matriz_pronta = False
    state.partida_criada = False
    state.current_player = None
    state.servidor_conectado = False
    state.iniciando_partida = True
    state.erro_conexao = None
    state.status_conexao = "Iniciando servidor local..."
    state.ws_url = LOCAL_WS_URL

    try:
        if _process is None or _process.poll() is not None:
            if _log_handle is not None:
                _log_handle.close()

            _log_handle = SERVER_LOG.open("w", encoding="utf-8")
            ambiente_servidor = os.environ.copy()
            if tamanho_mundo is not None:
                ambiente_servidor["TILE_GAME_WORLD_SIZE"] = str(tamanho_mundo)
            _process = subprocess.Popen([sys.executable, str(SERVER_DIR / "main.py")], cwd=SERVER_DIR, stdout=_log_handle, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), env=ambiente_servidor)
    except OSError as exc:
        state.iniciando_partida = False
        state.erro_conexao = f"Nao foi possivel iniciar o servidor: {exc}"
        print(state.erro_conexao)
        return False

    net.iniciar(LOCAL_WS_URL)
    return True


def encerrar():
    global _process, _log_handle

    if _process is not None and _process.poll() is None:
        _process.terminate()
        try:
            _process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _process.kill()
            _process.wait(timeout=2)

    _process = None
    if _log_handle is not None:
        _log_handle.close()
        _log_handle = None
