from .config import NOME_POR_TILES


def transformar_matriz_em_dict(matriz):
    altura = len(matriz)
    largura = len(matriz[0]) if altura else 0
    matriz_dict = [[None for _ in range(largura)] for _ in range(altura)]

    for y in range(altura):
        for x in range(largura):
            matriz_dict[y][x] = {
                "tile": NOME_POR_TILES[type(matriz[y][x])],
                "dono": matriz[y][x].current_player,
            }

    return matriz_dict
