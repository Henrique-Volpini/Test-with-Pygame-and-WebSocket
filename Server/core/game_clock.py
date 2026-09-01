import math
import time

from core.state import state


TICK_INTERVAL_SECONDS = 10.0
TICK_INTERVAL_MS = int(TICK_INTERVAL_SECONDS * 1000)


def _now(value):
    return time.monotonic() if value is None else float(value)


def reset(now=None):
    """Inicia o relogio autoritativo de uma nova partida."""
    instante = _now(now)
    state.tempo_partida = 0
    state.partida_inicio_monotonic = instante
    state.proximo_tick_monotonic = instante + TICK_INTERVAL_SECONDS
    state.tick_numero = 0


def _ensure_started(now):
    if (
        state.partida_inicio_monotonic is None
        or state.proximo_tick_monotonic is None
    ):
        reset(now)


def advance(now=None):
    """Avanca o relogio e devolve quantos ticks de jogo venceram."""
    if state.phase != "game":
        return 0

    instante = _now(now)
    _ensure_started(instante)
    inicio = state.partida_inicio_monotonic
    deadline = state.proximo_tick_monotonic

    state.tempo_partida = max(0, int(instante - inicio))
    if instante < deadline:
        return 0

    ticks_vencidos = int(
        math.floor((instante - deadline) / TICK_INTERVAL_SECONDS)
    ) + 1
    state.tick_numero += ticks_vencidos
    state.proximo_tick_monotonic += (
        ticks_vencidos * TICK_INTERVAL_SECONDS
    )
    return ticks_vencidos


def snapshot(now=None):
    """Retorna tempos em milissegundos para sincronizacao dos clientes."""
    instante = _now(now)
    if state.phase == "game":
        _ensure_started(instante)
        inicio = state.partida_inicio_monotonic
        deadline = state.proximo_tick_monotonic
        elapsed_ms = max(
            0,
            int(math.floor((instante - inicio) * 1000 + 1e-6)),
        )
        remaining_ms = max(
            0,
            min(
                TICK_INTERVAL_MS,
                int(math.ceil((deadline - instante) * 1000 - 1e-6)),
            ),
        )
    else:
        elapsed_ms = 0
        remaining_ms = TICK_INTERVAL_MS

    return {
        "match_time_ms": elapsed_ms,
        "tick_interval_ms": TICK_INTERVAL_MS,
        "tick_number": state.tick_numero,
        "tick_remaining_ms": remaining_ms,
    }
