import core.world as world
import core.tile as tile
from core.state import state

def construir_em_matriz(data):
    if "tile" not in data or "x, y" not in data or "player_id" not in data:
        return

    posicao = data["x, y"]
    if not isinstance(posicao, (list, tuple)) or len(posicao) != 2:
        return

    x, y = posicao
    if not isinstance(x, int) or not isinstance(y, int):
        return
    if not (0 <= y < len(state.matriz) and 0 <= x < len(state.matriz[0])):
        return
    if data["player_id"] not in state.players:
        return

    if data["tile"] == "grass":
        trocar_para_grass(data)
    
    elif data["tile"] == "city":
        trocar_para_city(data)

    elif data["tile"] == "town_center":
        trocar_para_town_center(data)

    elif data["tile"] == "lumberjack_cabin":
        trocar_para_lumberjackcabin(data)

    elif data["tile"] == "small_forest":
        trocar_para_small_florest(data)
    
    elif data["tile"] == "mountain":
        trocar_para_mountain(data)
    
    elif data["tile"] == "mine":
        trocar_para_mine(data)

    elif data["tile"] == "water":
        trocar_para_water(data)

    elif data["tile"] == "medium_forest":
        trocar_para_medium_forest(data)

    elif data["tile"] == "big_forest":
        trocar_para_big_forest(data)
    

def _trocar_e_registrar(data, pos, nova_construcao):
        x, y = pos
        tile_atual = state.matriz[y][x]

        dono_antigo_id = tile_atual.current_player
        if dono_antigo_id is not None:
            dono_antigo = state.players.get(dono_antigo_id)
            if dono_antigo:
                dono_antigo.remover_construcao_por_pos((x, y))

        state.matriz[y][x] = nova_construcao
        if data["player_id"] in state.players:
            state.players[data["player_id"]].registrar_construcao(state.matriz[y][x], (x, y))

        state.matriz_dict = world.transformar_matriz_em_dict(state.matriz)
        
def trocar_para_grass(data):
    x, y = data["x, y"]
    tile_atual = state.matriz[y][x]

    if not (isinstance(tile_atual, tile.Grass)):
        if tile.Grass.pagar(state.players[data["player_id"]].recursos):
            _trocar_e_registrar(data, (x, y), tile.Grass(current_player = data["player_id"]))

def trocar_para_city(data):
    x, y = data["x, y"]
    tile_atual = state.matriz[y][x]

    if not (isinstance(tile_atual, tile.City)):
        if tile.City.pagar(state.players[data["player_id"]].recursos):
            _trocar_e_registrar(data, (x, y), tile.City(current_player = data["player_id"]))

def trocar_para_town_center(data):

    raio = 1

    x, y = data["x, y"]
    tile_atual = state.matriz[y][x]
    tile_temporario = state.matriz[y][x]

    max_y = len(state.matriz)
    max_x = len(state.matriz[0])

    for y0 in range(max(0, y - raio), min(max_y, y + raio + 1)):
        for x0 in range(max(0, x - raio), min(max_x, x + raio + 1)):
            tile_temporario = state.matriz[y0][x0]
            if not (isinstance(tile_temporario, tile.Grass)):
                return

    if tile.TownCenter.pagar(state.players[data["player_id"]].recursos):
        for y0 in range(max(0, y - raio), min(max_y, y + raio + 1)):
            for x0 in range(max(0, x - raio), min(max_x, x + raio + 1)):
        
                if ((y0,x0) == (y,x)):
                    _trocar_e_registrar(data, (x, y), tile.TownCenter(current_player = data["player_id"]))
                else:
                    _trocar_e_registrar(data, (x0, y0), tile.City(current_player = data["player_id"]))       

def trocar_para_lumberjackcabin(data):
    x, y = data["x, y"]
    tile_atual = state.matriz[y][x]

    if not (isinstance(tile_atual, tile.LumberjackCabin) and tile_atual.current_player == data["player_id"]):
        if tile.LumberjackCabin.pagar(state.players[data["player_id"]].recursos):
            _trocar_e_registrar(data, (x, y), tile.LumberjackCabin(current_player = data["player_id"]))
            state.matriz[y][x].count_forest(state.matriz, (x, y))

def trocar_para_mountain(data):
    x, y = data["x, y"]
    tile_atual = state.matriz[y][x]

    if not (isinstance(tile_atual, tile.Mountain)):
        if tile.Mountain.pagar(state.players[data["player_id"]].recursos):
            _trocar_e_registrar(data, (x, y), tile.Mountain(current_player = data["player_id"]))

def trocar_para_mine(data):
    x, y = data["x, y"]
    tile_atual = state.matriz[y][x]

    if (isinstance(tile_atual, tile.Mountain)) or ((isinstance(tile_atual, tile.Mine)) and not tile_atual.current_player == data["player_id"]):
        if tile.Mine.pagar(state.players[data["player_id"]].recursos):
            _trocar_e_registrar(data, (x, y), tile.Mine(current_player = data["player_id"]))

def trocar_para_water(data):
    x, y = data["x, y"]
    tile_atual = state.matriz[y][x]

    if not (isinstance(tile_atual, tile.Water)):
        if tile.Water.pagar(state.players[data["player_id"]].recursos):
            _trocar_e_registrar(data, (x, y), tile.Water(current_player = data["player_id"]))

def trocar_para_small_florest(data):
    x, y = data["x, y"]
    tile_atual = state.matriz[y][x]

    if not (isinstance(tile_atual, tile.SmallForest) and tile_atual.current_player == data["player_id"]):
        if tile.SmallForest.pagar(state.players[data["player_id"]].recursos):
            _trocar_e_registrar(data, (x, y), tile.SmallForest(current_player = data["player_id"]))
            state.matriz[y][x].atualizar_lumberjackCabin(state.matriz, (x, y))

def trocar_para_medium_forest(data):
    x, y = data["x, y"]
    tile_atual = state.matriz[y][x]

    if not (isinstance(tile_atual, tile.MediumForest) and tile_atual.current_player == data["player_id"]):
        if tile.MediumForest.pagar(state.players[data["player_id"]].recursos):
            _trocar_e_registrar(data, (x, y), tile.MediumForest(current_player = data["player_id"]))
            state.matriz[y][x].atualizar_lumberjackCabin(state.matriz, (x, y))
 
def trocar_para_big_forest(data):
    x, y = data["x, y"]
    tile_atual = state.matriz[y][x]

    if not (isinstance(tile_atual, tile.BigForest) and tile_atual.current_player == data["player_id"]):
        if tile.BigForest.pagar(state.players[data["player_id"]].recursos):
            _trocar_e_registrar(data, (x, y), tile.BigForest(current_player = data["player_id"]))
            state.matriz[y][x].atualizar_lumberjackCabin(state.matriz, (x, y))
