import asyncio
import time

import core.evento_10_segundos as evento_10_segundos
import core.game_clock as game_clock
from core.state import state
from connections.transport.websocket_manager import broadcast_game


def process_due_ticks(now=None):
    ticks_vencidos = game_clock.advance(now)
    for _ in range(ticks_vencidos):
        evento_10_segundos.evento_10_segundos()
    return ticks_vencidos


def _next_wakeup(now):
    deadlines = [now + 1.0]
    if state.partida_inicio_monotonic is not None:
        proximo_segundo = (
            state.partida_inicio_monotonic + state.tempo_partida + 1
        )
        deadlines.append(proximo_segundo)
    if state.proximo_tick_monotonic is not None:
        deadlines.append(state.proximo_tick_monotonic)
    return max(0.01, min(deadlines) - now)


async def tick_loop():
    ultimo_segundo_publicado = None
    while True:
        if state.phase != "game":
            ultimo_segundo_publicado = None
            await asyncio.sleep(0.25)
            continue

        now = time.monotonic()
        ticks_vencidos = process_due_ticks(now)

        if state.connections and (
            ticks_vencidos
            or state.tempo_partida != ultimo_segundo_publicado
        ):
            await broadcast_game()
            ultimo_segundo_publicado = state.tempo_partida

        await asyncio.sleep(_next_wakeup(time.monotonic()))
