"""Exploracao privada e posse territorial, sempre validadas no servidor."""

from dataclasses import dataclass

import core.game_clock as game_clock
from core.recursos import Recursos
from core.state import state
from core.world.config import NOME_POR_TILES


EXPLORE_COST = {"gold": 20, "wood": 0, "food": 0}
CLAIM_COST = {"gold": 0, "wood": 30, "food": 10}
ACTION_RADIUS = 1
EXPLORE_TICKS = 1
NATURAL_TERRAIN = frozenset({"grass", "water", "mountain", "small_forest", "medium_forest", "big_forest"})


@dataclass
class ExplorationOrder:
    owner: str
    unit_id: str
    x: int
    y: int
    origin: tuple
    start_tick: int
    finish_tick: int


def is_busy(unit_id):
    return unit_id in state.exploration_orders


def terrain_name(cell):
    name = NOME_POR_TILES[type(cell)]
    if name in NATURAL_TERRAIN:
        return name
    base = getattr(cell, "base_terrain", None)
    if base in NATURAL_TERRAIN:
        return base
    return {"mine": "mountain", "dock": "water"}.get(name, "grass")


class ExplorationActionError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def initialize_players(matriz, jogadores):
    """Revela 5x5 e concede somente a cidade 3x3 ao iniciar a partida."""
    state.territory_owners = {}
    state.exploration_orders = {}
    for jogador in state.players.values():
        jogador.explored_tiles = set()
    height = len(matriz)
    width = len(matriz[0]) if height else 0
    for jogador in jogadores:
        jogador.explored_tiles = set()
        if jogador.posicao_inicial is None:
            continue
        cx, cy = jogador.posicao_inicial
        for y in range(max(0, cy - 2), min(height, cy + 3)):
            for x in range(max(0, cx - 2), min(width, cx + 3)):
                jogador.explored_tiles.add((x, y))
                if max(abs(x - cx), abs(y - cy)) <= 1:
                    state.territory_owners[x, y] = jogador.id


def is_explored(player_id, x, y):
    jogador = state.players.get(player_id)
    return jogador is not None and (x, y) in jogador.explored_tiles


def snapshot_matrix(player_id):
    """Conhecimento completo, faixa de terreno sob nevoa e restante oculto."""
    if state.matriz is None:
        return None
    width = len(state.matriz[0]) if state.matriz else 0
    result = [[None] * width for _ in state.matriz]
    jogador = state.players.get(player_id)
    if jogador is None:
        return result
    for x, y in jogador.explored_tiles:
        if not (0 <= y < len(result) and 0 <= x < width):
            continue
        cell = state.matriz[y][x]
        for py in range(max(0, y - 1), min(len(result), y + 2)):
            for px in range(max(0, x - 1), min(width, x + 2)):
                if (px, py) not in jogador.explored_tiles:
                    result[py][px] = {"tile": terrain_name(state.matriz[py][px]), "preview": True}
        result[y][x] = {
            "tile": NOME_POR_TILES[type(cell)],
            "dono": cell.current_player,
            "territorio": state.territory_owners.get((x, y)),
        }
    return result


def rules_snapshot():
    return {
        "explore_cost": dict(EXPLORE_COST),
        "claim_cost": dict(CLAIM_COST),
        "radius": ACTION_RADIUS,
        "total_ticks": EXPLORE_TICKS,
    }


def _validate_pioneer(player_id, unit_id, x, y):
    if (
        isinstance(x, bool) or isinstance(y, bool)
        or not isinstance(x, int) or not isinstance(y, int)
        or not state.matriz
        or not (0 <= y < len(state.matriz) and 0 <= x < len(state.matriz[0]))
    ):
        raise ExplorationActionError("invalid_position", "Escolha um tile dentro do mapa.")
    if not isinstance(unit_id, str) or not unit_id or len(unit_id) > 64:
        raise ExplorationActionError("invalid_unit", "Selecione um Pioneiro próprio.")
    jogador = state.players.get(player_id)
    unit = state.troops.get(unit_id)
    if jogador is None or unit is None or unit.hp <= 0 or unit.owner != player_id:
        raise ExplorationActionError("not_owner", "Selecione um Pioneiro próprio vivo.")
    if unit.kind != "pioneer":
        raise ExplorationActionError("not_pioneer", "Esta ação exige um Pioneiro.")
    if is_busy(unit_id):
        raise ExplorationActionError("pioneer_busy", "Este Pioneiro está explorando. Aguarde o ciclo completo terminar.")
    if max(abs(unit.x - x), abs(unit.y - y)) > ACTION_RADIUS:
        raise ExplorationActionError("out_of_range", "O tile precisa estar na área 3×3 ao redor do Pioneiro.")
    return jogador


def _pay(jogador, cost):
    recursos = Recursos(**cost)
    if not jogador.recursos.consigo_comprar(recursos):
        raise ExplorationActionError("insufficient_resources", "Recursos insuficientes para esta ação.")
    jogador.recursos.comprei(recursos)


def explore(player_id, unit_id, x, y, now=None):
    jogador = _validate_pioneer(player_id, unit_id, x, y)
    if is_explored(player_id, x, y):
        raise ExplorationActionError("already_explored", "Este tile já foi explorado.")
    if any(order.owner == player_id and (order.x, order.y) == (x, y) for order in state.exploration_orders.values()):
        raise ExplorationActionError("exploration_pending", "Um Pioneiro seu já está explorando este tile.")
    # O relogio real evita consumir ticks atrasados anteriores ao pedido.
    elapsed_ticks = game_clock.snapshot(now)["match_time_ms"] // game_clock.TICK_INTERVAL_MS
    start_tick = max(state.tick_numero, elapsed_ticks) + 1
    _pay(jogador, EXPLORE_COST)
    unit = state.troops[unit_id]
    unit.target = None
    unit.target_unit_id = None
    unit.ordered = False
    unit.status = "exploring"
    state.exploration_orders[unit_id] = ExplorationOrder(
        player_id, unit_id, x, y, (unit.x, unit.y), start_tick, start_tick + EXPLORE_TICKS,
    )


def orders_snapshot(player_id):
    return [
        {
            "unit_id": order.unit_id,
            "x": order.x,
            "y": order.y,
            "remaining_ticks": EXPLORE_TICKS,
            "total_ticks": EXPLORE_TICKS,
            "waiting_for_start": state.tick_numero < order.start_tick,
        }
        for order in sorted(state.exploration_orders.values(), key=lambda item: item.unit_id)
        if order.owner == player_id
    ]


def process_tick(tick_number):
    for unit_id, order in list(state.exploration_orders.items()):
        unit = state.troops.get(unit_id)
        player = state.players.get(order.owner)
        valid = (
            unit is not None and player is not None and unit.hp > 0
            and unit.owner == order.owner and unit.kind == "pioneer"
            and (unit.x, unit.y) == order.origin
            and max(abs(unit.x - order.x), abs(unit.y - order.y)) <= ACTION_RADIUS
        )
        if valid and tick_number < order.finish_tick:
            unit.status = "exploring"
            continue
        if valid and not is_explored(order.owner, order.x, order.y):
            player.explored_tiles.add((order.x, order.y))
            state.world_revision += 1
        if unit is not None and unit.status == "exploring":
            unit.status = "idle"
        del state.exploration_orders[unit_id]


def claim(player_id, unit_id, x, y):
    jogador = _validate_pioneer(player_id, unit_id, x, y)
    if not is_explored(player_id, x, y):
        raise ExplorationActionError("unexplored_tile", "Explore este tile antes de reivindicá-lo.")
    if state.territory_owners.get((x, y)) is not None:
        raise ExplorationActionError("territory_owned", "Este tile já pertence a um jogador.")
    # Defesa adicional para mundos importados com construcao sem posse do solo.
    if state.matriz[y][x].current_player not in (None, player_id):
        raise ExplorationActionError("territory_owned", "Este tile já pertence a outro jogador.")
    _pay(jogador, CLAIM_COST)
    state.territory_owners[x, y] = player_id
    state.world_revision += 1


def can_build(player_id, positions):
    """Pioneiro encosta na obra; no Centro, encosta no perimetro 3x3."""
    positions = set(positions)
    if not positions or any(
        not is_explored(player_id, x, y)
        or state.territory_owners.get((x, y)) != player_id
        for x, y in positions
    ):
        return False
    return any(
        unit.hp > 0 and unit.owner == player_id and unit.kind == "pioneer"
        and not is_busy(unit.id)
        and (unit.x, unit.y) not in positions
        and any(max(abs(unit.x - x), abs(unit.y - y)) == 1 for x, y in positions)
        for unit in state.troops.values()
    )
