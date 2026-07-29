import core.tile as tile

from core.state import state

from .config import (
    MOUNTAIN_TILE_THRESHOLD,
    WATER_BIRTH_MIN_NEIGHBORS,
    WATER_KEEP_MIN_NEIGHBORS,
    WATER_SMOOTHING_ITERATIONS,
    WATER_TILE_THRESHOLD,
)
from .smoothing import suavizar_lagos


def transformar_noise_em_tiles(mapa):
    matriz_tiles = [[None for _ in range(state.largura_grid)] for _ in range(state.altura_grid)]

    for y in range(state.altura_grid):
        for x in range(state.largura_grid):
            valor = mapa[y][x]
            if valor <= WATER_TILE_THRESHOLD:
                matriz_tiles[y][x] = tile.Water(current_player=None)
            elif valor < MOUNTAIN_TILE_THRESHOLD:
                matriz_tiles[y][x] = tile.Grass(current_player=None)
            else:
                matriz_tiles[y][x] = tile.Mountain(current_player=None)

    return suavizar_lagos(
        matriz_tiles,
        iteracoes=WATER_SMOOTHING_ITERATIONS,
        min_vizinhos_agua_manter=WATER_KEEP_MIN_NEIGHBORS,
        min_vizinhos_agua_nascer=WATER_BIRTH_MIN_NEIGHBORS,
    )
