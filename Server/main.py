from contextlib import asynccontextmanager, suppress
import asyncio

from fastapi import FastAPI, WebSocket

import core.world as world
from core.state import state
from connections.services.tick_event import tick_loop
from connections.transport.websocket_manager import websocket_handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    if state.matriz_dict is None:
        world.criar_matriz()

    task = asyncio.create_task(tick_loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(lifespan=lifespan)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_handler(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
