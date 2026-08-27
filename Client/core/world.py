import core.tile as tile
from core.state import state


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
    "big_forest": tile.BigForest,
}


def atualizar_matriz(matriz_do_servidor):
    """Valida e troca o mundo inteiro de forma atomica para a UI."""
    if not isinstance(matriz_do_servidor, list) or not matriz_do_servidor:
        return False

    with state.lock:
        if matriz_do_servidor == state.matriz_wire:
            state.matriz_pronta = True
            return True

    largura = None
    nova_matriz = []
    matriz_render = []

    for linha in matriz_do_servidor:
        if not isinstance(linha, list):
            return False
        if largura is None:
            largura = len(linha)
        if largura == 0 or len(linha) != largura:
            return False

        nova_linha = []
        linha_render = []
        for item in linha:
            if not isinstance(item, dict):
                return False
            nome_tile = item.get("tile")
            classe = TILES_POR_NOME.get(nome_tile)
            if classe is None:
                return False

            nova_linha.append(classe(current_player=item.get("dono")))
            linha_render.append(nome_tile)

        nova_matriz.append(nova_linha)
        matriz_render.append(linha_render)

    with state.lock:
        state.matriz = nova_matriz
        state.matriz_render = matriz_render
        state.matriz_wire = matriz_do_servidor
        state.altura_grid = len(nova_matriz)
        state.largura_grid = largura or 0
        state.world_revision += 1
        state.matriz_pronta = True

    return True
