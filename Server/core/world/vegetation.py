import core.tile as tile

from .config import BIG_FOREST_THRESHOLD, MEDIUM_FOREST_THRESHOLD, SMALL_FOREST_THRESHOLD


def transformar_noise_em_trees(mapa, matriz_base):
    # Comeca com a matriz base (agua/grama/montanha) e aplica arvores por cima.
    matriz_tiles = [linha[:] for linha in matriz_base]
    altura = len(mapa)
    largura = len(mapa[0]) if altura else 0

    for y in range(altura):
        for x in range(largura):
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
