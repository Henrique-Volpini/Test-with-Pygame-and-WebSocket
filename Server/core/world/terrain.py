import core.tile as tile

from .config import (
    MOUNTAIN_TILE_THRESHOLD,
    WATER_BIRTH_MIN_NEIGHBORS,
    WATER_KEEP_MIN_NEIGHBORS,
    WATER_SMOOTHING_ITERATIONS,
    WATER_TILE_THRESHOLD,
)
from .smoothing import suavizar_lagos


def transformar_noise_em_tiles(mapa):
    altura = len(mapa)
    largura = len(mapa[0]) if altura else 0
    matriz_tiles = [[None for _ in range(largura)] for _ in range(altura)]

    for y in range(altura):
        for x in range(largura):
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
