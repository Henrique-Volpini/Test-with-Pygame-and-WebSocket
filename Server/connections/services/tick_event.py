import asyncio

import core.evento_10_segundos as evento_10_segundos
from core.state import state
from connections.transport.websocket_manager import broadcast_game


async def tick_loop():
    while True:
        if state.phase != "game":
            await asyncio.sleep(1)
            continue

        state.tempo_partida += 1
        if state.tempo_partida % 10 == 0:
            evento_10_segundos.evento_10_segundos()

        if state.connections:
            await broadcast_game()

        await asyncio.sleep(1)
