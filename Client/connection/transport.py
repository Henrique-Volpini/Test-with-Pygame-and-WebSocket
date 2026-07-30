import asyncio
import json
import threading

# Guarda a thread do jogo
_thread = None
# Guarda o loop de eventos da conexao
_loop = None
# Guarda a conexao com o servidor
_ws = None
_stop_event = threading.Event()


def iniciar(uri, on_message, on_status=None):
    global _thread

    if _thread is None or not _thread.is_alive():
        _stop_event.clear()
        _thread = threading.Thread(
            target=_rodar_rede,
            args=(uri, on_message, on_status),
            daemon=True,
            name="rede-cliente",
        )
        _thread.start()


def enviar(dados):
    if _loop is None or _ws is None or _loop.is_closed():
        return False

    envio_async = _enviar_async(dados)
    try:
        asyncio.run_coroutine_threadsafe(envio_async, _loop)
    except RuntimeError:
        envio_async.close()
        return False
    return True


def parar():
    global _thread

    _stop_event.set()
    if _loop is not None and _ws is not None and not _loop.is_closed():
        try:
            asyncio.run_coroutine_threadsafe(_ws.close(), _loop)
        except RuntimeError:
            pass

    if _thread is not None and _thread.is_alive():
        _thread.join(timeout=3)
    _thread = None


def _rodar_rede(uri, on_message, on_status):
    # Funcao normal que a thread executa
    asyncio.run(_loop_rede(uri, on_message, on_status))


async def _loop_rede(uri, on_message, on_status):
    # Tenta conectar ate o servidor local terminar de iniciar.
    global _loop, _ws
    _loop = asyncio.get_running_loop()

    try:
        import websockets
    except ImportError:
        if on_status is not None:
            on_status(False, "A biblioteca websockets nao esta instalada.")
        _loop = None
        return

    while not _stop_event.is_set():
        try:
            async with websockets.connect(uri, open_timeout=2, max_size=16 * 1024 * 1024) as ws:
                _ws = ws
                if on_status is not None:
                    on_status(True, None)

                while not _stop_event.is_set():
                    data = await ws.recv()
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    on_message(data)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            if not _stop_event.is_set() and on_status is not None:
                on_status(False, str(exc))
            await asyncio.sleep(0.25)
        finally:
            _ws = None

    _loop = None


async def _enviar_async(dados):
    # Envia o JSON de verdade pela conexao
    if _ws is None:
        return
    try:
        await _ws.send(json.dumps(dados))
    except Exception:
        pass
