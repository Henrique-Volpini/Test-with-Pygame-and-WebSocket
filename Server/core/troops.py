"""Estado autoritativo de tropas, movimento e combate por tick.

O cliente apenas envia destinos. Toda simulacao (producao, pathfinding,
movimento, aggro, dano e mortes) acontece no servidor quando vence o tick de
10 segundos.
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from heapq import heappop, heappush

from core.state import state


LAND = "land"
BOAT = "boat"

UNIT_STATS = {
    LAND: {
        "max_hp": 12,
        "damage": 4,
        "attack_range": 1,
        "movement": 2,
        "aggro_range": 6,
        "cap": 24,
    },
    BOAT: {
        "max_hp": 22,
        "damage": 6,
        "attack_range": 2,
        "movement": 3,
        "aggro_range": 8,
        "cap": 12,
    },
}

RECRUITMENT_STATS = {
    LAND: {
        "building": "GuardHouse",
        "cost_gold": 75,
        "total_ticks": 2,
    },
    BOAT: {
        "building": "Dock",
        "cost_gold": 120,
        "total_ticks": 3,
    },
}

MAX_RECRUITMENT_QUEUE = 5

MAX_FRIENDLY_UNITS_PER_TILE = 4

_BUILDING_KIND = {
    "GuardHouse": LAND,
    "Dock": BOAT,
}
_LAND_BLOCKERS = frozenset({"Water", "Dock", "Mountain", "Mine"})
_BOAT_TERRAIN = frozenset({"Water", "Dock"})
_NEIGHBORS = ((0, -1), (1, 0), (0, 1), (-1, 0))
_SPAWN_OFFSETS = (
    (0, 0),
    (0, -1),
    (1, 0),
    (0, 1),
    (-1, 0),
    (1, -1),
    (1, 1),
    (-1, 1),
    (-1, -1),
)

_COMPONENT_CACHE = {}
_COMPONENT_CONTEXT = None


class TroopActionError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@dataclass
class Troop:
    id: str
    owner: str
    kind: str
    x: int
    y: int
    hp: int
    max_hp: int
    target: tuple | None = None
    status: str = "idle"

    # Campos internos. Na rede, target e sempre uma coordenada [x, y].
    ordered: bool = False
    target_unit_id: str | None = None

    def to_dict(self, viewer_id=None):
        return {
            "id": self.id,
            "owner": self.owner,
            "is_mine": self.owner == viewer_id,
            "kind": self.kind,
            "x": self.x,
            "y": self.y,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "target": list(self.target) if self.target is not None else None,
            "status": self.status,
        }


@dataclass
class RecruitmentItem:
    id: str
    owner: str
    unit_kind: str
    remaining_ticks: int
    total_ticks: int
    cost_gold: int
    waiting_for_start: bool = True

    def to_dict(self):
        return {
            "id": self.id,
            "unit_kind": self.unit_kind,
            "remaining_ticks": self.remaining_ticks,
            "total_ticks": self.total_ticks,
            "cost_gold": self.cost_gold,
            "waiting_for_start": self.waiting_for_start,
        }


def reset():
    """Limpa a simulacao para o inicio de uma nova partida."""
    global _COMPONENT_CONTEXT
    state.troops = {}
    state.next_troop_id = 1
    state.recruitment_queues = {}
    state.next_recruitment_id = 1
    _COMPONENT_CACHE.clear()
    _COMPONENT_CONTEXT = None


def snapshot(viewer_id=None):
    return [
        troop.to_dict(viewer_id)
        for troop in sorted(state.troops.values(), key=_troop_sort_key)
    ]


def _troop_sort_key(troop):
    try:
        sequence = int(troop.id.rsplit("-", 1)[-1])
    except (AttributeError, TypeError, ValueError):
        sequence = 0
    return sequence, str(troop.id)


def _dimensions():
    height = len(state.matriz) if state.matriz is not None else 0
    width = len(state.matriz[0]) if height else 0
    return width, height


def _in_bounds(x, y):
    width, height = _dimensions()
    return 0 <= x < width and 0 <= y < height


def _terrain_passable(kind, x, y):
    if not _in_bounds(x, y):
        return False
    tile_name = type(state.matriz[y][x]).__name__
    if kind == BOAT:
        return tile_name in _BOAT_TERRAIN
    return tile_name not in _LAND_BLOCKERS


def _units_at(x, y, *, exclude_id=None):
    return [
        troop
        for troop in state.troops.values()
        if troop.hp > 0
        and troop.id != exclude_id
        and troop.x == x
        and troop.y == y
    ]


def _can_enter(troop, x, y, *, respect_units=True):
    if not _terrain_passable(troop.kind, x, y):
        return False
    if not respect_units:
        return True

    occupants = _units_at(x, y, exclude_id=troop.id)
    if any(other.owner != troop.owner for other in occupants):
        return False
    return len(occupants) < MAX_FRIENDLY_UNITS_PER_TILE


def _manhattan(first, second):
    return abs(first[0] - second[0]) + abs(first[1] - second[1])


def _terrain_components(kind):
    """Rotula ilhas navegaveis/caminhaveis uma vez por revisao do mundo."""
    global _COMPONENT_CONTEXT
    width, height = _dimensions()
    context = (id(state.matriz), state.terrain_revision, width, height)
    if context != _COMPONENT_CONTEXT:
        _COMPONENT_CACHE.clear()
        _COMPONENT_CONTEXT = context
    cached = _COMPONENT_CACHE.get(kind)
    if cached is not None:
        return cached

    components = [[-1 for _ in range(width)] for _ in range(height)]
    component_id = 0
    for start_y in range(height):
        for start_x in range(width):
            if (
                components[start_y][start_x] != -1
                or not _terrain_passable(kind, start_x, start_y)
            ):
                continue
            components[start_y][start_x] = component_id
            frontier = deque([(start_x, start_y)])
            while frontier:
                x, y = frontier.popleft()
                for dx, dy in _NEIGHBORS:
                    neighbor_x, neighbor_y = x + dx, y + dy
                    if (
                        not _in_bounds(neighbor_x, neighbor_y)
                        or components[neighbor_y][neighbor_x] != -1
                        or not _terrain_passable(kind, neighbor_x, neighbor_y)
                    ):
                        continue
                    components[neighbor_y][neighbor_x] = component_id
                    frontier.append((neighbor_x, neighbor_y))
            component_id += 1

    _COMPONENT_CACHE[kind] = components
    return components


def _terrain_reachable(troop, goals):
    if not goals or not _in_bounds(troop.x, troop.y):
        return False
    components = _terrain_components(troop.kind)
    component_id = components[troop.y][troop.x]
    if component_id < 0:
        return False
    return any(components[y][x] == component_id for x, y in goals)


def _enemy_on(owner, x, y):
    enemies = [
        troop
        for troop in _units_at(x, y)
        if troop.owner != owner
    ]
    return min(enemies, key=_troop_sort_key) if enemies else None


def _attack_goals(troop, target):
    attack_range = UNIT_STATS[troop.kind]["attack_range"]
    tx, ty = target
    width, height = _dimensions()
    goals = set()
    for y in range(max(0, ty - attack_range), min(height, ty + attack_range + 1)):
        remaining = attack_range - abs(y - ty)
        for x in range(max(0, tx - remaining), min(width, tx + remaining + 1)):
            if _terrain_passable(troop.kind, x, y):
                goals.add((x, y))
    return goals


def _goals_for(troop, target):
    enemy = _enemy_on(troop.owner, *target)
    if enemy is not None:
        return _attack_goals(troop, target), enemy
    if _terrain_passable(troop.kind, *target):
        return {target}, None
    return set(), None


def _find_path(troop, goals, *, respect_units):
    if not goals:
        return None
    start = (troop.x, troop.y)
    if start in goals:
        return [start]

    def heuristic(position):
        return min(_manhattan(position, goal) for goal in goals)

    # A* com desempate pelo menor h. Em mapas abertos ele segue um corredor
    # curto em direcao ao destino, em vez de varrer o retangulo inteiro como
    # uma BFS faria. O contador preserva a ordem deterministica dos vizinhos.
    sequence = 0
    initial_h = heuristic(start)
    frontier = [(initial_h, initial_h, sequence, 0, start)]
    costs = {start: 0}
    previous = {start: None}
    reached = None
    while frontier:
        _priority, _remaining, _sequence, cost, current = heappop(frontier)
        if cost != costs.get(current):
            continue
        if current in goals:
            reached = current
            break

        x, y = current
        for dx, dy in _NEIGHBORS:
            neighbor = (x + dx, y + dy)
            if not _can_enter(
                troop,
                neighbor[0],
                neighbor[1],
                respect_units=respect_units,
            ):
                continue
            next_cost = cost + 1
            if next_cost >= costs.get(neighbor, float("inf")):
                continue
            costs[neighbor] = next_cost
            previous[neighbor] = current
            remaining = heuristic(neighbor)
            sequence += 1
            heappush(
                frontier,
                (
                    next_cost + remaining,
                    remaining,
                    sequence,
                    next_cost,
                    neighbor,
                ),
            )

    if reached is None:
        return None

    path = []
    cursor = reached
    while cursor is not None:
        path.append(cursor)
        cursor = previous[cursor]
    path.reverse()
    return path


def issue_order(player_id, unit_id, x, y):
    """Registra um destino; nenhuma acao fisica ocorre fora do tick."""
    if not isinstance(unit_id, str) or not unit_id:
        raise TroopActionError("invalid_unit", "Informe uma tropa valida.")
    if (
        isinstance(x, bool)
        or isinstance(y, bool)
        or not isinstance(x, int)
        or not isinstance(y, int)
        or not _in_bounds(x, y)
    ):
        raise TroopActionError(
            "invalid_destination",
            "O destino da tropa esta fora do mapa.",
        )

    troop = state.troops.get(unit_id)
    if troop is None or troop.hp <= 0:
        raise TroopActionError("unit_not_found", "Essa tropa nao existe mais.")
    if troop.owner != player_id:
        raise TroopActionError(
            "forbidden",
            "Voce so pode dar ordens as suas proprias tropas.",
        )

    target = (x, y)
    goals, enemy = _goals_for(troop, target)
    if not goals:
        domain = "agua" if troop.kind == BOAT else "terra"
        raise TroopActionError(
            "invalid_destination",
            f"Essa tropa so pode se mover por {domain}.",
        )
    if not _terrain_reachable(troop, goals):
        raise TroopActionError(
            "unreachable_destination",
            "Nao existe um caminho valido ate esse destino.",
        )
    # A busca completa pertence ao tick autoritativo. Assim, spam de ordens
    # apenas substitui o unico destino pendente da unidade e nunca bloqueia o
    # event loop com dezenas de BFS entre dois ticks.
    troop.target = target
    troop.target_unit_id = enemy.id if enemy is not None else None
    troop.ordered = True
    troop.status = "moving" if (troop.x, troop.y) not in goals else "idle"
    return troop


def _new_troop(owner, kind, x, y):
    stats = UNIT_STATS[kind]
    troop = Troop(
        id=f"troop-{state.next_troop_id}",
        owner=owner,
        kind=kind,
        x=x,
        y=y,
        hp=stats["max_hp"],
        max_hp=stats["max_hp"],
    )
    state.next_troop_id += 1
    state.troops[troop.id] = troop
    return troop


def _kind_count(owner, kind):
    return sum(
        troop.hp > 0 and troop.owner == owner and troop.kind == kind
        for troop in state.troops.values()
    )


def _reserved_count(owner, kind):
    return sum(
        item.owner == owner and item.unit_kind == kind
        for queue in state.recruitment_queues.values()
        for item in queue
    )


def _capacity_used(owner, kind):
    return _kind_count(owner, kind) + _reserved_count(owner, kind)


def _spawn_position(owner, kind, building_x, building_y):
    probe = Troop("", owner, kind, building_x, building_y, 1, 1)
    for dx, dy in _SPAWN_OFFSETS:
        x, y = building_x + dx, building_y + dy
        if _can_enter(probe, x, y, respect_units=True):
            return x, y
    return None


def _building_at(x, y):
    if not _in_bounds(x, y):
        return None, None, None
    current_tile = state.matriz[y][x]
    tile_name = type(current_tile).__name__
    kind = _BUILDING_KIND.get(tile_name)
    owner = getattr(current_tile, "current_player", None)
    return current_tile, kind, owner


def has_pending_recruitment(x, y):
    return bool(state.recruitment_queues.get((x, y)))


def _recruitment_availability(viewer_id, x, y, kind, owner):
    if owner != viewer_id:
        return False, "not_owner"
    if kind not in RECRUITMENT_STATS:
        return False, "not_recruitment_building"

    queue = state.recruitment_queues.get((x, y), [])
    if len(queue) >= MAX_RECRUITMENT_QUEUE:
        return False, "queue_full"
    if _capacity_used(viewer_id, kind) >= UNIT_STATS[kind]["cap"]:
        return False, "army_cap_reached"

    player = state.players.get(viewer_id)
    if player is None or player.recursos.gold < RECRUITMENT_STATS[kind]["cost_gold"]:
        return False, "insufficient_gold"
    return True, None


def recruit(player_id, x, y):
    if (
        isinstance(x, bool)
        or isinstance(y, bool)
        or not isinstance(x, int)
        or not isinstance(y, int)
        or not _in_bounds(x, y)
    ):
        raise TroopActionError(
            "invalid_recruitment_position",
            "A construcao de recrutamento esta fora do mapa.",
        )

    _building, kind, owner = _building_at(x, y)
    if owner != player_id:
        raise TroopActionError(
            "not_owner",
            "Voce so pode recrutar em suas proprias construcoes.",
        )
    if kind not in RECRUITMENT_STATS:
        raise TroopActionError(
            "not_recruitment_building",
            "Essa construcao nao recruta tropas.",
        )

    available, reason = _recruitment_availability(
        player_id,
        x,
        y,
        kind,
        owner,
    )
    if not available:
        messages = {
            "queue_full": "A fila dessa construcao ja possui cinco tropas.",
            "army_cap_reached": "O limite desse tipo de tropa ja foi reservado.",
            "insufficient_gold": "Ouro insuficiente para recrutar essa tropa.",
        }
        raise TroopActionError(reason, messages[reason])

    stats = RECRUITMENT_STATS[kind]
    player = state.players[player_id]
    player.recursos.gold -= stats["cost_gold"]
    item = RecruitmentItem(
        id=f"recruit-{state.next_recruitment_id}",
        owner=player_id,
        unit_kind=kind,
        remaining_ticks=stats["total_ticks"],
        total_ticks=stats["total_ticks"],
        cost_gold=stats["cost_gold"],
    )
    state.next_recruitment_id += 1
    state.recruitment_queues.setdefault((x, y), []).append(item)
    return item


def _process_recruitment():
    """Avanca filas usando somente limites completos do tick global.

    Uma ordem criada durante o ciclo atual apenas comeca no proximo limite;
    esse limite nao reduz ``remaining_ticks``. Quando uma ordem termina, a
    seguinte e promovida no mesmo limite, mas tambem so consome seu primeiro
    tick completo no limite posterior.
    """
    empty_positions = []
    for x, y in sorted(state.recruitment_queues, key=lambda pos: (pos[1], pos[0])):
        queue = state.recruitment_queues[(x, y)]
        if not queue:
            empty_positions.append((x, y))
            continue

        item = queue[0]
        _building, kind, owner = _building_at(x, y)
        if kind != item.unit_kind or owner != item.owner:
            # A regra de construcao impede este caso. Se estado externo for
            # corrompido, a reserva permanece intacta em vez de sumir.
            continue

        if item.waiting_for_start:
            item.waiting_for_start = False
            continue

        if item.remaining_ticks > 0:
            item.remaining_ticks -= 1
        if item.remaining_ticks > 0:
            continue

        position = _spawn_position(owner, kind, x, y)
        if position is None:
            # Pronta: permanece em zero ate surgir espaco, bloqueando a fila
            # serial sem perder ouro nem capacidade reservada.
            continue

        _new_troop(owner, kind, *position)
        queue.pop(0)
        if queue:
            # A proxima ordem inicia quando a anterior deixa o predio. Ela
            # ainda precisa atravessar todos os seus ticks globais completos.
            queue[0].waiting_for_start = False
        else:
            empty_positions.append((x, y))

    for position in empty_positions:
        if not state.recruitment_queues.get(position):
            state.recruitment_queues.pop(position, None)


def command_buildings_snapshot(viewer_id):
    buildings = []
    if state.matriz is None:
        return buildings
    type_names = {
        "TownCenter": "town_center",
        "GuardHouse": "guard_house",
        "Dock": "dock",
    }
    for y, row in enumerate(state.matriz):
        for x, current_tile in enumerate(row):
            building_type = type_names.get(type(current_tile).__name__)
            if building_type is None:
                continue
            owner = getattr(current_tile, "current_player", None)
            is_mine = owner == viewer_id
            kind = _BUILDING_KIND.get(type(current_tile).__name__)
            can_recruit, unavailable_reason = _recruitment_availability(
                viewer_id,
                x,
                y,
                kind,
                owner,
            )
            queue = state.recruitment_queues.get((x, y), []) if is_mine else []
            buildings.append(
                {
                    "x": x,
                    "y": y,
                    "type": building_type,
                    "owner": owner,
                    "is_mine": is_mine,
                    "queue": [item.to_dict() for item in queue],
                    "can_recruit": can_recruit,
                    "unavailable_reason": unavailable_reason,
                }
            )
    return buildings


def army_snapshot(viewer_id):
    return {
        "land": _kind_count(viewer_id, LAND),
        "boat": _kind_count(viewer_id, BOAT),
        "land_cap": UNIT_STATS[LAND]["cap"],
        "boat_cap": UNIT_STATS[BOAT]["cap"],
    }


def _valid_enemy(unit, unit_id):
    target = state.troops.get(unit_id)
    if target is None or target.hp <= 0 or target.owner == unit.owner:
        return None
    return target


def _refresh_targets():
    living = sorted(state.troops.values(), key=_troop_sort_key)
    for troop in living:
        if troop.hp <= 0:
            continue

        tracked = _valid_enemy(troop, troop.target_unit_id)
        if tracked is not None:
            troop.target = (tracked.x, tracked.y)
            continue
        troop.target_unit_id = None

        # Uma ordem explicita de movimento nunca e substituida por aggro.
        if troop.ordered:
            continue

        candidates = [
            enemy
            for enemy in living
            if enemy.hp > 0
            and enemy.owner != troop.owner
            and _manhattan((troop.x, troop.y), (enemy.x, enemy.y))
            <= UNIT_STATS[troop.kind]["aggro_range"]
        ]
        if not candidates:
            troop.target = None
            troop.status = "idle"
            continue

        candidates.sort(
            key=lambda item: (
                _manhattan((troop.x, troop.y), (item.x, item.y)),
                item.hp,
                _troop_sort_key(item),
            )
        )
        for enemy in candidates:
            goals = _attack_goals(troop, (enemy.x, enemy.y))
            if _terrain_reachable(troop, goals):
                troop.target = (enemy.x, enemy.y)
                troop.target_unit_id = enemy.id
                troop.status = "moving"
                break


def _move_troops():
    for troop in sorted(state.troops.values(), key=_troop_sort_key):
        if troop.hp <= 0 or troop.target is None:
            continue

        goals, enemy = _goals_for(troop, troop.target)
        if not goals or not _terrain_reachable(troop, goals):
            troop.target = None
            troop.target_unit_id = None
            troop.ordered = False
            troop.status = "idle"
            continue

        path = _find_path(troop, goals, respect_units=True)
        if path is None:
            # A conectividade do terreno ja foi comprovada acima. Portanto,
            # esta unidade esta apenas aguardando aliados liberarem passagem;
            # nao repetimos uma segunda busca global sem ocupantes.
            troop.status = "moving"
            continue

        steps = min(UNIT_STATS[troop.kind]["movement"], len(path) - 1)
        for next_x, next_y in path[1 : steps + 1]:
            if not _can_enter(troop, next_x, next_y, respect_units=True):
                break
            troop.x, troop.y = next_x, next_y

        at_goal = (troop.x, troop.y) in goals
        if at_goal and enemy is None and (troop.x, troop.y) == troop.target:
            troop.target = None
            troop.target_unit_id = None
            troop.ordered = False
            troop.status = "idle"
        else:
            troop.status = "moving"


def _preferred_attack_target(attacker, enemies):
    tracked = _valid_enemy(attacker, attacker.target_unit_id)
    if tracked in enemies:
        return tracked
    return min(
        enemies,
        key=lambda item: (
            _manhattan((attacker.x, attacker.y), (item.x, item.y)),
            item.hp,
            _troop_sort_key(item),
        ),
    )


def _resolve_combat():
    living = sorted(state.troops.values(), key=_troop_sort_key)
    pending_damage = defaultdict(int)
    for attacker in living:
        if attacker.hp <= 0:
            continue
        attack_range = UNIT_STATS[attacker.kind]["attack_range"]
        enemies = [
            target
            for target in living
            if target.hp > 0
            and target.owner != attacker.owner
            and _manhattan((attacker.x, attacker.y), (target.x, target.y))
            <= attack_range
        ]
        if not enemies:
            continue
        victim = _preferred_attack_target(attacker, enemies)
        pending_damage[victim.id] += UNIT_STATS[attacker.kind]["damage"]
        attacker.status = "attacking"

    # Dano simultaneo evita vantagem artificial pela ordem dos IDs.
    for troop_id in sorted(pending_damage):
        target = state.troops.get(troop_id)
        if target is not None:
            target.hp = max(0, target.hp - pending_damage[troop_id])

    dead_troops = sorted(
        (troop for troop in state.troops.values() if troop.hp <= 0),
        key=_troop_sort_key,
    )
    dead_ids = [troop.id for troop in dead_troops]
    for troop_id in dead_ids:
        state.troops.pop(troop_id, None)

    if not dead_ids:
        return
    dead = set(dead_ids)
    for troop in state.troops.values():
        if troop.target_unit_id in dead:
            troop.target_unit_id = None
            if troop.ordered:
                troop.status = "moving"
            else:
                troop.target = None
                troop.status = "idle"


def process_tick(tick_number=None):
    """Executa exatamente um ciclo deterministico da simulacao militar."""
    if tick_number is None:
        tick_number = state.tick_numero
    tick_number = max(1, int(tick_number))
    _refresh_targets()
    _move_troops()
    _resolve_combat()
    # Recrutamento e estritamente manual. Conclusoes ocorrem no fim do tick e
    # as novas unidades so podem agir a partir do ciclo seguinte.
    _process_recruitment()
