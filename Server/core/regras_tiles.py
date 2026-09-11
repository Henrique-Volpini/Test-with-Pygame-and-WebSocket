import core.world as world
import core.tile as tile
import core.troops as troops
import core.exploration as exploration
from core.state import state

def construir_em_matriz(data):
    if "tile" not in data or "x, y" not in data or "player_id" not in data:
        return False

    posicao = data["x, y"]
    if not isinstance(posicao, (list, tuple)) or len(posicao) != 2:
        return False

    x, y = posicao
    if (
        isinstance(x, bool)
        or isinstance(y, bool)
        or not isinstance(x, int)
        or not isinstance(y, int)
    ):
        return False
    if (
        not isinstance(state.matriz, list)
        or not state.matriz
        or not isinstance(state.matriz[0], list)
        or not state.matriz[0]
        or not (0 <= y < len(state.matriz) and 0 <= x < len(state.matriz[0]))
    ):
        return False
    if data["player_id"] not in state.players:
        return False

    if troops.has_pending_recruitment(x, y):
        return False

    player_id = data["player_id"]
    if data["tile"] == "town_center":
        if x < 1 or y < 1 or x + 1 >= len(state.matriz[0]) or y + 1 >= len(state.matriz):
            return False
        positions = {(px, py) for py in range(y - 1, y + 2) for px in range(x - 1, x + 2)}
    else:
        positions = {(x, y)}
    if not exploration.can_build(player_id, positions):
        return False
    # Protege de terraformacao a faixa de combate ao redor de toda a obra.
    if any(
        tropa.hp > 0 and tropa.owner != player_id
        and any(abs(tropa.x - px) <= 1 and abs(tropa.y - py) <= 1 for px, py in positions)
        for tropa in state.troops.values()
    ):
        return False
    tile_atual = state.matriz[y][x]
    if tile_atual.current_player not in (None, player_id):
        return False
    if any(
        tropa.hp > 0 and tropa.x == x and tropa.y == y
        for tropa in state.troops.values()
    ):
        return False
    revisao_anterior = state.world_revision

    if data["tile"] == "grass":
        trocar_para_grass(data)
    
    elif data["tile"] == "city":
        trocar_para_city(data)

    elif data["tile"] == "town_center":
        trocar_para_town_center(data)

    elif data["tile"] == "guard_house":
        trocar_para_guard_house(data)

    elif data["tile"] == "dock":
        trocar_para_dock(data)

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

    return state.world_revision != revisao_anterior

def _trocar_e_registrar(data, pos, nova_construcao):
        x, y = pos
        tile_atual = state.matriz[y][x]

        nova_construcao.base_terrain = exploration.terrain_name(tile_atual)
        assinatura_anterior = _assinatura_terreno(tile_atual)
        assinatura_nova = _assinatura_terreno(nova_construcao)

        dono_antigo_id = tile_atual.current_player
        if dono_antigo_id is not None:
            dono_antigo = state.players.get(dono_antigo_id)
            if dono_antigo:
                dono_antigo.remover_construcao_por_pos((x, y))

        state.matriz[y][x] = nova_construcao
        if data["player_id"] in state.players:
            state.players[data["player_id"]].registrar_construcao(state.matriz[y][x], (x, y))

        state.matriz_dict = world.transformar_matriz_em_dict(state.matriz)
        if assinatura_anterior != assinatura_nova:
            state.terrain_revision += 1
        state.world_revision += 1


def _assinatura_terreno(tile_atual):
    terrestre = not isinstance(
        tile_atual,
        (tile.Water, tile.Dock, tile.Mountain, tile.Mine),
    )
    aquatico = isinstance(tile_atual, (tile.Water, tile.Dock))
    return terrestre, aquatico
        
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
            if (
                not isinstance(tile_temporario, tile.Grass)
                or tile_temporario.current_player not in (
                    None,
                    data["player_id"],
                )
                or any(
                    tropa.hp > 0 and tropa.x == x0 and tropa.y == y0
                    for tropa in state.troops.values()
                )
                or troops.has_pending_recruitment(x0, y0)
            ):
                return

    if tile.TownCenter.pagar(state.players[data["player_id"]].recursos):
        for y0 in range(max(0, y - raio), min(max_y, y + raio + 1)):
            for x0 in range(max(0, x - raio), min(max_x, x + raio + 1)):
        
                if ((y0,x0) == (y,x)):
                    _trocar_e_registrar(data, (x, y), tile.TownCenter(current_player = data["player_id"]))
                else:
                    _trocar_e_registrar(data, (x0, y0), tile.City(current_player = data["player_id"]))       

def trocar_para_guard_house(data):
    """Ergue a guarda exclusivamente sobre uma cidade do construtor."""
    x, y = data["x, y"]
    tile_atual = state.matriz[y][x]
    player_id = data["player_id"]

    if not (
        isinstance(tile_atual, tile.City)
        and tile_atual.current_player == player_id
    ):
        return

    if tile.GuardHouse.pagar(state.players[player_id].recursos):
        _trocar_e_registrar(
            data,
            (x, y),
            tile.GuardHouse(current_player=player_id),
        )


def _tem_terra_adjacente(x, y):
    altura = len(state.matriz)
    largura = len(state.matriz[0])
    for deslocamento_x, deslocamento_y in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        vizinho_x = x + deslocamento_x
        vizinho_y = y + deslocamento_y
        if not (0 <= vizinho_x < largura and 0 <= vizinho_y < altura):
            continue

        vizinho = state.matriz[vizinho_y][vizinho_x]
        # Um dock ocupa agua e, portanto, nao pode prolongar artificialmente
        # a costa para permitir uma cadeia de docks em mar aberto.
        if not isinstance(vizinho, (tile.Water, tile.Dock)):
            return True
    return False


def trocar_para_dock(data):
    """Ergue um porto em agua livre, ortogonalmente junto da costa."""
    x, y = data["x, y"]
    tile_atual = state.matriz[y][x]
    player_id = data["player_id"]

    if not isinstance(tile_atual, tile.Water):
        return
    if tile_atual.current_player not in (None, player_id):
        return
    if not _tem_terra_adjacente(x, y):
        return

    if tile.Dock.pagar(state.players[player_id].recursos):
        _trocar_e_registrar(
            data,
            (x, y),
            tile.Dock(current_player=player_id),
        )

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
