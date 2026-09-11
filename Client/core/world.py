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
    "guard_house": tile.GuardHouse,
    "water": tile.Water,
    "dock": tile.Dock,
    "medium_forest": tile.MediumForest,
    "big_forest": tile.BigForest,
}


def atualizar_matriz(matriz_do_servidor):
    """Valida e troca o mundo inteiro de forma atomica para a UI."""
    if not isinstance(matriz_do_servidor, list) or not matriz_do_servidor:
        return False

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
            if item is None:
                nova_linha.append(None)
                linha_render.append(None)
                continue
            if not isinstance(item, dict):
                return False
            if any(item.get(key) is not None and not isinstance(item.get(key), str) for key in ("dono", "territorio")):
                return False
            nome_tile = item.get("tile")
            if not isinstance(nome_tile, str):
                return False
            classe = TILES_POR_NOME.get(nome_tile)
            if classe is None:
                return False

            if "preview" in item and not isinstance(item["preview"], bool):
                return False
            if item.get("preview") is True:
                if nome_tile not in {"grass", "water", "mountain", "small_forest", "medium_forest", "big_forest"} or "dono" in item or "territorio" in item:
                    return False
                nova_linha.append(None)
                linha_render.append(nome_tile)
                continue

            nova_linha.append(classe(current_player=item.get("dono")))
            linha_render.append(nome_tile)

        nova_matriz.append(nova_linha)
        matriz_render.append(linha_render)

    with state.lock:
        # A igualdade Python considera True == 1; valide tipos antes do cache.
        if matriz_do_servidor == state.matriz_wire:
            state.matriz_pronta = True
            return True
        state.matriz = nova_matriz
        state.matriz_render = matriz_render
        state.matriz_wire = matriz_do_servidor
        state.altura_grid = len(nova_matriz)
        state.largura_grid = largura or 0
        state.world_revision += 1
        state.matriz_pronta = True

    return True
