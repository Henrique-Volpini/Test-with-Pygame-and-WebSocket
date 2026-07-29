import core.tile as tile

from core.state import state

from .config import BIG_FOREST_THRESHOLD, MEDIUM_FOREST_THRESHOLD, SMALL_FOREST_THRESHOLD


def transformar_noise_em_trees(mapa):
    # Comeca com a matriz base (agua/grama/montanha) e aplica arvores por cima.
    matriz_tiles = [linha[:] for linha in state.matriz]

    for y in range(state.altura_grid):
        for x in range(state.largura_grid):
            valor = mapa[y][x]

            if (valor > BIG_FOREST_THRESHOLD) and (isinstance(matriz_tiles[y][x], tile.Grass)):
                matriz_tiles[y][x] = tile.BigForest(current_player=None)
            elif (valor > MEDIUM_FOREST_THRESHOLD) and (
                isinstance(matriz_tiles[y][x], tile.Grass)
            ):
                matriz_tiles[y][x] = tile.MediumForest(current_player=None)
            elif (valor > SMALL_FOREST_THRESHOLD) and (
                isinstance(matriz_tiles[y][x], tile.Grass)
            ):
                matriz_tiles[y][x] = tile.SmallForest(current_player=None)

    return matriz_tiles
