import asyncio

import core.evento_10_segundos as evento_10_segundos
from core.state import state
from connections.services.game_runtime import build_update
from connections.transport.websocket_manager import enqueue_message


async def tick_loop():
    while True:
        state.tempo_partida += 1

        if state.tempo_partida % 10 == 0:
            evento_10_segundos.evento_10_segundos()

        if state.connections:
            for conn in list(state.connections):
                player_id = state.player_id_by_conn.get(conn)
                if player_id in state.players:
                    message = build_update(player_id)
                    await enqueue_message(conn, message)

        await asyncio.sleep(1)
