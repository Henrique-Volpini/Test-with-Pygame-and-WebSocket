import core.tile as tile
from core.state import state

state.altura_grid = 90
state.largura_grid = 120

state.matriz = [[tile.Grass() for _ in range(state.largura_grid)] for _ in range(state.altura_grid)]

TILES_POR_NOME = {
    "grass": tile.Grass,
    "madeireiro": tile.LumberjackCabin,
    "small_forest": tile.SmallForest,
    "mountain": tile.Mountain,
    "mine": tile.Mine,
    "town_center": tile.TownCenter,
    "city": tile.City,
    "water": tile.Water,
    "medium_forest": tile.MediumForest,
    "big_forest": tile.BigForest
}

def atualizar_matriz(matriz_do_servidor):
    for y, linha in enumerate(matriz_do_servidor):
        for x, item in enumerate(linha):
            classe = TILES_POR_NOME[item["tile"]]
            obj = classe(current_player=item["dono"])
            state.matriz[y][x] = obj

    state.matriz_pronta = True

    

