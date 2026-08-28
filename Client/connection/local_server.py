import importlib.util
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading

from connection import net
from core.state import state


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = PROJECT_ROOT / "Server"
SERVER_LOG = PROJECT_ROOT / "server.log"

_process = None
_log_handle = None
_lifecycle_lock = threading.RLock()
LOCAL_WS_URL = "ws://127.0.0.1:8765/ws"


def porta_servidor_em_uso():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        return sock.connect_ex(("127.0.0.1", 8765)) == 0
    finally:
        sock.close()


def iniciar(tamanho_mundo=None, seed=None, game_code=""):
    global _process, _log_handle

    if isinstance(tamanho_mundo, bool) or (
        tamanho_mundo is not None
        and (not isinstance(tamanho_mundo, int) or not 1 <= tamanho_mundo <= 200)
    ):
        with state.lock:
            state.erro_conexao = "O tamanho do mundo deve estar entre 1 e 200."
        return False
    if (
        isinstance(seed, bool)
        or (
            seed is not None
            and (not isinstance(seed, int) or not 0 <= seed <= 2_147_483_647)
        )
    ):
        with state.lock:
            state.erro_conexao = "A seed deve estar entre 0 e 2147483647."
        return False

    with state.lock:
        hospedagem_em_andamento = (
            state.iniciando_partida and state.session_mode == "host"
        )
        interromper_conexao_remota = (
            state.iniciando_partida and state.session_mode == "connect"
        )

    if hospedagem_em_andamento:
        with _lifecycle_lock:
            if _process is not None and _process.poll() is None:
                return True

    if interromper_conexao_remota:
        net.parar()

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
        with state.lock:
            state.erro_conexao = "Dependencias ausentes: " + ", ".join(ausentes)
            erro = state.erro_conexao
        print(erro)
        return False

    if porta_servidor_em_uso():
        with state.lock:
            state.erro_conexao = "A porta 8765 ja esta sendo usada por outro servidor. Feche o processo antigo."
            erro = state.erro_conexao
        print(erro)
        return False

    host_token = secrets.token_urlsafe(32)
    state.resetar_sessao(
        LOCAL_WS_URL,
        "Iniciando servidor local...",
        "host",
        lobby_code=game_code,
    )

    with _lifecycle_lock:
        try:
            if _process is None or _process.poll() is not None:
                if _log_handle is not None:
                    _log_handle.close()

                _log_handle = SERVER_LOG.open("w", encoding="utf-8")
                ambiente_servidor = os.environ.copy()
                if tamanho_mundo is not None:
                    ambiente_servidor["TILE_GAME_WORLD_SIZE"] = str(tamanho_mundo)
                if seed is not None:
                    ambiente_servidor["TILE_GAME_WORLD_SEED"] = str(seed)
                ambiente_servidor["TILE_GAME_HOST_TOKEN"] = host_token
                ambiente_servidor["TILE_GAME_ROOM_CODE"] = game_code
                _process = subprocess.Popen(
                    [sys.executable, str(SERVER_DIR / "main.py")],
                    cwd=SERVER_DIR,
                    stdout=_log_handle,
                    stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    env=ambiente_servidor,
                )
        except OSError as exc:
            with state.lock:
                state.iniciando_partida = False
                state.erro_conexao = f"Nao foi possivel iniciar o servidor: {exc}"
                erro = state.erro_conexao
            print(erro)
            return False

    net.iniciar(
        LOCAL_WS_URL,
        host_token=host_token,
        room_code=game_code,
    )
    return True


def encerrar():
    global _process, _log_handle

    with _lifecycle_lock:
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
