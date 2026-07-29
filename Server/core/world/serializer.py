from core.state import state

from .config import NOME_POR_TILES


def transformar_matriz_em_dict(matriz):
    matriz_dict = [[None for _ in range(state.largura_grid)] for _ in range(state.altura_grid)]

    for y in range(state.altura_grid):
        for x in range(state.largura_grid):
            matriz_dict[y][x] = {
                "tile": NOME_POR_TILES[type(matriz[y][x])],
                "dono": matriz[y][x].current_player,
            }

    return matriz_dict
