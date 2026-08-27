import asyncio
import json
import threading


class _ConnectionRuntime:
    def __init__(self):
        self.stop_event = threading.Event()
        self.thread = None
        self.loop = None
        self.ws = None


_runtime = None
_runtime_lock = threading.RLock()


def iniciar(uri, on_message, on_status=None):
    global _runtime

    with _runtime_lock:
        if _runtime is not None and _runtime.thread.is_alive():
            return

        runtime = _ConnectionRuntime()
        runtime.thread = threading.Thread(
            target=_rodar_rede,
            args=(runtime, uri, on_message, on_status),
            daemon=True,
            name="rede-cliente",
        )
        _runtime = runtime
        runtime.thread.start()


def enviar(dados):
    with _runtime_lock:
        runtime = _runtime
        if runtime is None:
            return False
        loop = runtime.loop
        ws = runtime.ws

    if loop is None or ws is None or loop.is_closed():
        return False

    envio_async = _enviar_async(ws, dados)
    try:
        asyncio.run_coroutine_threadsafe(envio_async, loop)
    except RuntimeError:
        envio_async.close()
        return False
    return True


def parar():
    global _runtime

    with _runtime_lock:
        runtime = _runtime
        if runtime is None:
            return
        runtime.stop_event.set()
        loop = runtime.loop
        ws = runtime.ws
        thread = runtime.thread

    if loop is not None and ws is not None and not loop.is_closed():
        try:
            asyncio.run_coroutine_threadsafe(ws.close(), loop)
        except RuntimeError:
            pass

    if thread.is_alive() and thread is not threading.current_thread():
        thread.join(timeout=3)

    with _runtime_lock:
        if _runtime is runtime:
            _runtime = None


def _runtime_atual(runtime):
    with _runtime_lock:
        return _runtime is runtime


def _rodar_rede(runtime, uri, on_message, on_status):
    asyncio.run(_loop_rede(runtime, uri, on_message, on_status))


async def _loop_rede(runtime, uri, on_message, on_status):
    try:
        import websockets
    except ImportError:
        if on_status is not None and _runtime_atual(runtime):
            on_status(False, "A biblioteca websockets nao esta instalada.")
        return

    with _runtime_lock:
        runtime.loop = asyncio.get_running_loop()

    try:
        while not runtime.stop_event.is_set():
            try:
                async with websockets.connect(
                    uri,
                    open_timeout=2,
                    max_size=16 * 1024 * 1024,
                ) as ws:
                    with _runtime_lock:
                        runtime.ws = ws

                    if on_status is not None and _runtime_atual(runtime):
                        on_status(True, None)

                    while not runtime.stop_event.is_set():
                        data = await ws.recv()
                        try:
                            data = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        if _runtime_atual(runtime):
                            on_message(data)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                if (
                    not runtime.stop_event.is_set()
                    and on_status is not None
                    and _runtime_atual(runtime)
                ):
                    on_status(False, str(exc))
                await asyncio.sleep(0.25)
            finally:
                with _runtime_lock:
                    runtime.ws = None
    finally:
        with _runtime_lock:
            runtime.loop = None


async def _enviar_async(ws, dados):
    try:
        await ws.send(json.dumps(dados))
    except Exception:
        pass
