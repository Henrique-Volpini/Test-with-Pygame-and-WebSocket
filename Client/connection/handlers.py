import time

import core.world as world
from core.generation_settings import (
    calcular_percentuais_biomas,
    validar_parametros_mapa,
)
from core.player import Player
from core.state import state


COMMAND_BUILDING_TYPES = frozenset(
    {"town_center", "guard_house", "dock"}
)
COMMAND_UNIT_KINDS = frozenset({"land", "boat"})
COMMAND_UNIT_RULES = {
    "land": {"total_ticks": 2, "cost_gold": 75},
    "boat": {"total_ticks": 3, "cost_gold": 120},
}
COMMAND_QUEUE_LIMIT = 5
COMMAND_ARMY_CAPS = {"land": 24, "boat": 12}
COMMAND_BUILDING_UNIT_KIND = {
    "guard_house": "land",
    "dock": "boat",
}
COMMAND_UNAVAILABLE_REASONS = frozenset(
    {
        "not_owner",
        "not_recruitment_building",
        "queue_full",
        "army_cap_reached",
        "insufficient_gold",
    }
)


def _marcar_partida_pronta():
    if (
        state.server_phase == "game"
        and state.player_id_criado
        and state.matriz_pronta
    ):
        state.partida_criada = True
        state.iniciando_partida = False
        state.estado_jogo = "partida"


def _validar_relogio(data):
    chaves = (
        "match_time_ms",
        "tick_interval_ms",
        "tick_number",
        "tick_remaining_ms",
    )
    presentes = [chave in data for chave in chaves]
    if not any(presentes):
        # Mantem compatibilidade com um servidor antigo durante a migracao.
        return None
    if not all(presentes):
        return False

    match_time_ms = data["match_time_ms"]
    tick_interval_ms = data["tick_interval_ms"]
    tick_number = data["tick_number"]
    tick_remaining_ms = data["tick_remaining_ms"]
    if any(
        isinstance(valor, bool) or not isinstance(valor, int)
        for valor in (
            match_time_ms,
            tick_interval_ms,
            tick_number,
            tick_remaining_ms,
        )
    ):
        return False
    if (
        match_time_ms < 0
        or not 1 <= tick_interval_ms <= 600_000
        or tick_number < 0
        or not 0 <= tick_remaining_ms <= tick_interval_ms
    ):
        return False

    return {
        "match_time_ms": match_time_ms,
        "tick_interval_ms": tick_interval_ms,
        "tick_number": tick_number,
        "tick_remaining_ms": tick_remaining_ms,
    }


def _validar_tropas(value, player_id, largura, altura):
    if value is None:
        # Compatibilidade com snapshots anteriores ao sistema militar.
        return None
    if (
        not isinstance(value, list)
        or not isinstance(largura, int)
        or not isinstance(altura, int)
        or largura <= 0
        or altura <= 0
        or len(value) > 10_000
    ):
        return False

    tropas = []
    ids = set()
    for item in value:
        if not isinstance(item, dict):
            return False

        unit_id = item.get("id")
        owner = item.get("owner")
        is_mine = item.get("is_mine")
        kind = item.get("kind")
        x = item.get("x")
        y = item.get("y")
        hp = item.get("hp")
        max_hp = item.get("max_hp")
        target = item.get("target")
        status = item.get("status")

        if (
            not isinstance(unit_id, str)
            or not unit_id
            or len(unit_id) > 64
            or unit_id in ids
            or not isinstance(owner, str)
            or not owner
            or len(owner) > 256
            or not isinstance(is_mine, bool)
            or kind not in ("land", "boat")
            or isinstance(x, bool)
            or not isinstance(x, int)
            or isinstance(y, bool)
            or not isinstance(y, int)
            or not 0 <= x < largura
            or not 0 <= y < altura
            or isinstance(hp, bool)
            or not isinstance(hp, int)
            or isinstance(max_hp, bool)
            or not isinstance(max_hp, int)
            or not 0 <= hp <= max_hp
            or not 1 <= max_hp <= 1_000_000
            or status not in ("idle", "moving", "attacking")
            or (
                player_id is not None
                and is_mine != (owner == player_id)
            )
        ):
            return False

        if target is not None:
            if (
                not isinstance(target, (list, tuple))
                or len(target) != 2
                or any(
                    isinstance(coordenada, bool)
                    or not isinstance(coordenada, int)
                    for coordenada in target
                )
                or not 0 <= target[0] < largura
                or not 0 <= target[1] < altura
            ):
                return False
            target = [target[0], target[1]]

        ids.add(unit_id)
        tropas.append(
            {
                "id": unit_id,
                "owner": owner,
                "is_mine": is_mine,
                "kind": kind,
                "x": x,
                "y": y,
                "hp": hp,
                "max_hp": max_hp,
                "target": target,
                "status": status,
            }
        )
    return tropas


def _validar_fila_recrutamento(value):
    if not isinstance(value, list) or len(value) > COMMAND_QUEUE_LIMIT:
        return False

    fila = []
    ids = set()
    for queue_index, item in enumerate(value):
        if not isinstance(item, dict):
            return False

        command_id = item.get("id")
        unit_kind = item.get("unit_kind")
        remaining_ticks = item.get("remaining_ticks")
        total_ticks = item.get("total_ticks")
        cost_gold = item.get("cost_gold")
        waiting_for_start = item.get("waiting_for_start")
        if (
            not isinstance(command_id, str)
            or not command_id
            or len(command_id) > 64
            or command_id in ids
            or not isinstance(unit_kind, str)
            or unit_kind not in COMMAND_UNIT_KINDS
            or isinstance(remaining_ticks, bool)
            or not isinstance(remaining_ticks, int)
            or isinstance(total_ticks, bool)
            or not isinstance(total_ticks, int)
            or not 0 <= remaining_ticks <= total_ticks
            or total_ticks < 1
            or isinstance(cost_gold, bool)
            or not isinstance(cost_gold, int)
            or cost_gold < 0
            or not isinstance(waiting_for_start, bool)
        ):
            return False

        unit_rule = COMMAND_UNIT_RULES[unit_kind]
        if (
            total_ticks != unit_rule["total_ticks"]
            or cost_gold != unit_rule["cost_gold"]
            or (waiting_for_start and remaining_ticks != total_ticks)
            or (queue_index > 0 and not waiting_for_start)
        ):
            return False

        ids.add(command_id)
        fila.append(
            {
                "id": command_id,
                "unit_kind": unit_kind,
                "remaining_ticks": remaining_ticks,
                "total_ticks": total_ticks,
                "cost_gold": cost_gold,
                "waiting_for_start": waiting_for_start,
            }
        )
    return fila


def _validar_command_buildings(value, player_id, largura, altura):
    if (
        not isinstance(value, list)
        or not isinstance(largura, int)
        or not isinstance(altura, int)
        or largura <= 0
        or altura <= 0
        or len(value) > largura * altura
    ):
        return False

    buildings = []
    positions = set()
    for item in value:
        if not isinstance(item, dict):
            return False

        x = item.get("x")
        y = item.get("y")
        building_type = item.get("type")
        owner = item.get("owner")
        is_mine = item.get("is_mine")
        queue = _validar_fila_recrutamento(item.get("queue"))
        can_recruit = item.get("can_recruit")
        unavailable_reason = item.get("unavailable_reason")
        if (
            isinstance(x, bool)
            or not isinstance(x, int)
            or isinstance(y, bool)
            or not isinstance(y, int)
            or not 0 <= x < largura
            or not 0 <= y < altura
            or (x, y) in positions
            or not isinstance(building_type, str)
            or building_type not in COMMAND_BUILDING_TYPES
            or not isinstance(owner, str)
            or not owner
            or len(owner) > 256
            or not isinstance(is_mine, bool)
            or (
                player_id is not None
                and is_mine != (owner == player_id)
            )
            or queue is False
            or not isinstance(can_recruit, bool)
            or not (
                unavailable_reason is None
                or (
                    isinstance(unavailable_reason, str)
                    and unavailable_reason in COMMAND_UNAVAILABLE_REASONS
                )
            )
        ):
            return False

        expected_kind = COMMAND_BUILDING_UNIT_KIND.get(building_type)
        if (
            (expected_kind is None and (queue or can_recruit))
            or (
                expected_kind is not None
                and any(
                    command["unit_kind"] != expected_kind
                    for command in queue
                )
            )
            or (not is_mine and (queue or can_recruit))
        ):
            return False

        positions.add((x, y))
        buildings.append(
            {
                "x": x,
                "y": y,
                "type": building_type,
                "owner": owner,
                "is_mine": is_mine,
                "queue": queue,
                "can_recruit": can_recruit,
                "unavailable_reason": unavailable_reason,
            }
        )
    return buildings


def _validar_army(value):
    if not isinstance(value, dict):
        return False

    keys = ("land", "boat", "land_cap", "boat_cap")
    if not all(key in value for key in keys):
        return False
    if any(
        isinstance(value[key], bool)
        or not isinstance(value[key], int)
        or value[key] < 0
        for key in keys
    ):
        return False
    if value["land"] > value["land_cap"] or value["boat"] > value["boat_cap"]:
        return False
    if any(
        value[f"{kind}_cap"] != cap
        for kind, cap in COMMAND_ARMY_CAPS.items()
    ):
        return False
    return {key: value[key] for key in keys}


def _validar_consistencia_militar(tropas, buildings, army, recursos):
    gold = recursos.get("gold")
    if isinstance(gold, bool) or not isinstance(gold, int) or gold < 0:
        return False

    live = {kind: 0 for kind in COMMAND_UNIT_KINDS}
    for troop in tropas:
        if troop["is_mine"] and troop["hp"] > 0:
            live[troop["kind"]] += 1
    if any(army[kind] != live[kind] for kind in COMMAND_UNIT_KINDS):
        return False

    reserved = {kind: 0 for kind in COMMAND_UNIT_KINDS}
    for building in buildings:
        if not building["is_mine"]:
            continue
        for command in building["queue"]:
            reserved[command["unit_kind"]] += 1

    used = {
        kind: live[kind] + reserved[kind]
        for kind in COMMAND_UNIT_KINDS
    }
    if any(
        used[kind] > army[f"{kind}_cap"]
        for kind in COMMAND_UNIT_KINDS
    ):
        return False

    for building in buildings:
        building_type = building["type"]
        kind = COMMAND_BUILDING_UNIT_KIND.get(building_type)
        if not building["is_mine"]:
            expected_can_recruit = False
            expected_reason = "not_owner"
        elif kind is None:
            expected_can_recruit = False
            expected_reason = "not_recruitment_building"
        elif len(building["queue"]) >= COMMAND_QUEUE_LIMIT:
            expected_can_recruit = False
            expected_reason = "queue_full"
        elif used[kind] >= army[f"{kind}_cap"]:
            expected_can_recruit = False
            expected_reason = "army_cap_reached"
        elif gold < COMMAND_UNIT_RULES[kind]["cost_gold"]:
            expected_can_recruit = False
            expected_reason = "insufficient_gold"
        else:
            expected_can_recruit = True
            expected_reason = None

        if (
            building["can_recruit"] != expected_can_recruit
            or building["unavailable_reason"] != expected_reason
        ):
            return False
    return True


def _aplicar_snapshot(data):
    recebido_em = time.monotonic()
    if data.get("fase") != "game":
        return False

    relogio = _validar_relogio(data)
    if relogio is False:
        return False

    recursos = data.get("recursos")
    if not isinstance(recursos, dict):
        return False
    if not all(chave in recursos for chave in ("gold", "wood", "food")):
        return False

    posicao_inicial = data.get("posicao_inicial")
    if posicao_inicial is not None and (
        not isinstance(posicao_inicial, (list, tuple))
        or len(posicao_inicial) != 2
        or any(
            isinstance(coordenada, bool) or not isinstance(coordenada, int)
            for coordenada in posicao_inicial
        )
    ):
        return False

    matriz = data.get("matriz")

    snapshot_player_id = data.get("player_id")
    if snapshot_player_id is not None and (
        not isinstance(snapshot_player_id, str)
        or not snapshot_player_id
        or len(snapshot_player_id) > 256
    ):
        return False
    with state.lock:
        player_id_atual = state.player_id
        largura_atual = state.largura_grid
        altura_atual = state.altura_grid
    if (
        snapshot_player_id is not None
        and player_id_atual is not None
        and snapshot_player_id != player_id_atual
    ):
        return False
    viewer_id = snapshot_player_id or player_id_atual

    if matriz is not None and isinstance(matriz, list) and matriz:
        altura_tropas = len(matriz)
        largura_tropas = len(matriz[0]) if isinstance(matriz[0], list) else 0
    else:
        largura_tropas = largura_atual
        altura_tropas = altura_atual
    tropas = _validar_tropas(
        data.get("troops"),
        viewer_id,
        largura_tropas,
        altura_tropas,
    )
    if tropas is False:
        return False

    command_buildings = None
    if "command_buildings" in data:
        command_buildings = _validar_command_buildings(
            data["command_buildings"],
            viewer_id,
            largura_tropas,
            altura_tropas,
        )
        if command_buildings is False:
            return False

    army = None
    if "army" in data:
        army = _validar_army(data["army"])
        if army is False:
            return False

    if (
        tropas is not None
        and command_buildings is not None
        and army is not None
        and not _validar_consistencia_militar(
            tropas,
            command_buildings,
            army,
            recursos,
        )
    ):
        return False

    if posicao_inicial is not None:
        if matriz is not None:
            if (
                not isinstance(matriz, list)
                or not matriz
                or not isinstance(matriz[0], list)
                or not matriz[0]
                or not 0 <= posicao_inicial[0] < len(matriz[0])
                or not 0 <= posicao_inicial[1] < len(matriz)
            ):
                return False
        else:
            with state.lock:
                if not (
                    0 <= posicao_inicial[0] < state.largura_grid
                    and 0 <= posicao_inicial[1] < state.altura_grid
                ):
                    return False

    if matriz is not None and not world.atualizar_matriz(matriz):
        return False

    with state.lock:
        if matriz is None and not state.matriz_pronta:
            return False
        state.server_phase = "game"
        state.recursos_pendentes = {
            "gold": recursos["gold"],
            "wood": recursos["wood"],
            "food": recursos["food"],
        }
        state.spawn_position = (
            tuple(posicao_inicial)
            if posicao_inicial is not None
            else None
        )
        if tropas is not None:
            state.troops = tropas
        if command_buildings is not None:
            state.command_buildings = command_buildings
        if army is not None:
            state.army = army
        if relogio is not None:
            state.match_time_ms = relogio["match_time_ms"]
            state.tick_interval_ms = relogio["tick_interval_ms"]
            state.tick_number = relogio["tick_number"]
            state.tick_remaining_ms = relogio["tick_remaining_ms"]
            state.tick_snapshot_monotonic = recebido_em
        if state.current_player is not None:
            state.current_player.recursos.atualizar_recursos(state.recursos_pendentes)
        _marcar_partida_pronta()

    return True


def _validar_jogadores(value):
    if not isinstance(value, list):
        return None

    jogadores = []
    for item in value:
        if not isinstance(item, dict):
            return None
        player_id = item.get("id")
        nome = item.get("nome")
        if not isinstance(player_id, str) or not player_id:
            return None
        if not isinstance(nome, str) or not nome:
            return None
        jogadores.append(
            {
                "id": player_id,
                "name": nome,
                "is_host": bool(item.get("is_host")),
                "is_self": bool(item.get("is_self")),
            }
        )
    return jogadores


def _aplicar_lobby(data):
    if data.get("fase") != "lobby":
        return False

    jogadores = _validar_jogadores(data.get("jogadores"))
    if jogadores is None:
        return False

    seed = data.get("seed")
    largura = data.get("largura")
    altura = data.get("altura")
    revision = data.get("revisao")
    world_revision = data.get("world_revision")
    try:
        parametros_mapa = validar_parametros_mapa(data.get("parametros_mapa"))
    except ValueError:
        return False
    composicao_mapa = data.get("composicao_mapa")
    if not isinstance(composicao_mapa, dict) or not all(
        isinstance(composicao_mapa.get(key), (int, float))
        and not isinstance(composicao_mapa.get(key), bool)
        and 0 <= composicao_mapa.get(key) <= 100
        for key in ("water", "plains", "mountains", "forests")
    ):
        composicao_mapa = calcular_percentuais_biomas(parametros_mapa)
    if (
        isinstance(seed, bool)
        or not isinstance(seed, int)
        or not 0 <= seed <= 2_147_483_647
        or isinstance(largura, bool)
        or not isinstance(largura, int)
        or isinstance(altura, bool)
        or not isinstance(altura, int)
        or not 1 <= largura <= 200
        or not 1 <= altura <= 200
        or isinstance(revision, bool)
        or not isinstance(revision, int)
        or isinstance(world_revision, bool)
        or not isinstance(world_revision, int)
    ):
        return False

    matriz = data.get("matriz")
    if matriz is not None and not world.atualizar_matriz(matriz):
        return False

    with state.lock:
        if matriz is None and not state.matriz_pronta:
            return False
        state.server_phase = "lobby"
        state.estado_jogo = "lobby"
        state.iniciando_partida = False
        state.partida_criada = False
        state.lobby_revision = revision
        state.lobby_world_revision = world_revision
        state.lobby_seed = seed
        state.lobby_size = largura
        state.lobby_map_params = parametros_mapa
        state.lobby_map_composition = {
            key: composicao_mapa[key]
            for key in ("water", "plains", "mountains", "forests")
        }
        state.lobby_players = jogadores
        state.lobby_is_host = bool(data.get("is_host"))
        state.lobby_generating = bool(data.get("gerando"))
        state.lobby_status = str(data.get("status") or "")
        state.lobby_error = data.get("erro")

    return True


def _campo_erro(value, fallback):
    return value if isinstance(value, str) and value else fallback


def receber(data):
    # Esta funcao roda na thread de rede. So publica estados completos.
    if not isinstance(data, dict) or not isinstance(data.get("tipo"), str):
        print("Recebido payload com formato invalido:", data)
        return

    tipo = data["tipo"]
    if tipo in ("update", "resposta"):
        if not _aplicar_snapshot(data):
            print("Recebido snapshot de partida com formato invalido.")
            return
        return

    if tipo == "lobby_estado":
        if not _aplicar_lobby(data):
            print("Recebido estado de lobby com formato invalido.")
        return

    if tipo == "bem_vindo":
        player_id = data.get("player_id")
        if not isinstance(player_id, str) or not player_id:
            print("Recebido payload de boas-vindas invalido.")
            return

        with state.lock:
            state.player_id = player_id
            state.player_id_criado = True
            state.current_player = Player(player_id=player_id)
            state.lobby_is_host = bool(data.get("is_host"))
            state.server_phase = data.get("fase")
            if state.recursos_pendentes is not None:
                state.current_player.recursos.atualizar_recursos(
                    state.recursos_pendentes
                )
            _marcar_partida_pronta()

        print(f"Bem-vindo, jogador {player_id}!")
        return

    if tipo == "erro":
        action = _campo_erro(data.get("acao"), "unknown")
        code = _campo_erro(data.get("codigo"), "unknown_error")
        mensagem = _campo_erro(
            data.get("mensagem"),
            "Ação recusada pelo servidor.",
        )
        with state.lock:
            if state.estado_jogo == "partida":
                state.last_action_error_revision += 1
                state.last_action_error = {
                    "action": action,
                    "code": code,
                    "message": mensagem,
                    "revision": state.last_action_error_revision,
                }
            state.lobby_error = mensagem
            state.lobby_status = mensagem
            state.lobby_generating = False
        print(mensagem)
        return

    print("Recebido payload com tipo desconhecido:", tipo)
