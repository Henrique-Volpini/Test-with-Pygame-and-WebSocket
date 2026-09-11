import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1] / "Server"

SCENARIO = """
import copy
from unittest.mock import patch

import core.exploration as exploration
import core.game_clock as game_clock
import core.player as player
import core.spawn as spawn
import core.tile as tile
import core.troops as troops
import core.world as world
from core.state import state
from connections.services.game_runtime import build_update, process_game_action
from connections.services.tick_event import process_due_ticks

first = player.Player("first", None, 1, True)
second = player.Player("second", None, 2)
state.players = {first.id: first, second.id: second}
state.phase = "game"
state.matriz = [[tile.Grass() for _ in range(17)] for _ in range(17)]
troops.reset()
spawn.posicionar_jogadores(state.matriz, state.players.values())
state.matriz_dict = world.transformar_matriz_em_dict(state.matriz)
game_clock.reset(now=100)

def visible_positions(matrix):
    return {
        (x, y)
        for y, row in enumerate(matrix)
        for x, cell in enumerate(row)
        if cell is not None
    }

def known_positions(matrix):
    return {
        (x, y)
        for y, row in enumerate(matrix)
        for x, cell in enumerate(row)
        if cell is not None and not cell.get("preview", False)
    }

def preview_positions(known):
    return {
        (x + dx, y + dy)
        for x, y in known
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        if 0 <= x + dx < 17 and 0 <= y + dy < 17
    } - known

def perform(action, unit, x, y, owner=first.id, **extra):
    with patch("time.monotonic", return_value=105):
        return process_game_action(
            {"tipo": action, "unit_id": unit.id, "x": x, "y": y, **extra},
            owner,
        )

def assert_rejected(data, owner=first.id):
    resources = {p.id: p.recursos.to_dict() for p in state.players.values()}
    known = {p.id: set(p.explored_tiles) for p in state.players.values()}
    territory = dict(state.territory_owners)
    matrix = [list(row) for row in state.matriz]
    revision = state.world_revision
    orders = copy.deepcopy(state.exploration_orders)
    with patch("time.monotonic", return_value=105):
        error, phase = process_game_action(data, owner)
    assert error is not None and error["tipo"] == "erro", (data, error, phase)
    assert phase is None
    assert {p.id: p.recursos.to_dict() for p in state.players.values()} == resources
    assert {p.id: set(p.explored_tiles) for p in state.players.values()} == known
    assert state.territory_owners == territory
    assert state.matriz == matrix
    assert state.world_revision == revision
    assert state.exploration_orders == orders
"""


def run_scenario(source):
    result = subprocess.run(
        [sys.executable, "-c", SCENARIO + "\n" + textwrap.dedent(source)],
        cwd=SERVER_DIR,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Processo isolado falhou ({result.returncode}).\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


class ExplorationRuntimeTests(unittest.TestCase):
    def test_spawn_reveals_only_five_by_five_and_grants_city_territory(self):
        run_scenario(
            """
            for owner in (first, second):
                cx, cy = owner.posicao_inicial
                expected = {
                    (x, y)
                    for y in range(cy - 2, cy + 3)
                    for x in range(cx - 2, cx + 3)
                }
                owned = {
                    (x, y)
                    for y in range(cy - 1, cy + 2)
                    for x in range(cx - 1, cx + 2)
                }
                assert owner.explored_tiles == expected
                assert known_positions(exploration.snapshot_matrix(owner.id)) == expected
                assert known_positions(build_update(owner.id)["matriz"]) == expected
                fringe = preview_positions(expected)
                assert visible_positions(exploration.snapshot_matrix(owner.id)) == expected | fringe
                assert all(
                    exploration.snapshot_matrix(owner.id)[y][x] == {"tile": "grass", "preview": True}
                    for x, y in fringe
                )
                assert {
                    pos for pos, value in state.territory_owners.items()
                    if value == owner.id
                } == owned
                snapshot = exploration.snapshot_matrix(owner.id)
                assert all(snapshot[y][x]["territorio"] == owner.id for x, y in owned)
                assert all(snapshot[y][x]["territorio"] is None for x, y in expected - owned)
                assert all(exploration.is_explored(owner.id, *pos) for pos in expected)
                assert not exploration.is_explored(owner.id, 8, 8)
            assert first.explored_tiles.isdisjoint(second.explored_tiles)
            assert exploration.snapshot_matrix(first.id)[14][14] is None
            assert exploration.snapshot_matrix(second.id)[2][2] is None
            assert build_update(first.id, include_matrix=False)["matriz"] is None
            """
        )

    def test_exploration_charges_once_and_requires_one_whole_ten_second_turn(self):
        run_scenario(
            """
            pioneer = troops._new_troop(first.id, troops.PIONEER, 4, 2)
            before_first = set(first.explored_tiles)
            before_second = set(second.explored_tiles)
            before_territory = dict(state.territory_owners)
            error, phase = perform("explorar_tile", pioneer, 5, 3)
            assert error is None and phase == "game"
            assert first.recursos.to_dict() == {"gold": 480, "wood": 500, "food": 500}
            assert first.explored_tiles == before_first
            assert pioneer.status == "exploring"
            assert (pioneer.x, pioneer.y) == (4, 2)
            assert build_update(first.id)["exploration_orders"] == [{
                "unit_id": pioneer.id, "x": 5, "y": 3,
                "remaining_ticks": 1, "total_ticks": 1, "waiting_for_start": True,
            }]
            assert build_update(first.id)["exploration_rules"]["total_ticks"] == 1
            assert build_update(second.id)["exploration_orders"] == []
            assert exploration.snapshot_matrix(first.id)[3][5] == {"tile": "grass", "preview": True}
            assert process_due_ticks(now=109.999) == 0
            assert first.explored_tiles == before_first
            assert process_due_ticks(now=110) == 1
            assert first.explored_tiles == before_first
            assert pioneer.status == "exploring"
            order = build_update(first.id)["exploration_orders"][0]
            assert order["remaining_ticks"] == 1 and order["waiting_for_start"] is False
            assert process_due_ticks(now=119.999) == 0
            assert first.explored_tiles == before_first
            assert process_due_ticks(now=120) == 1
            assert first.explored_tiles == before_first | {(5, 3)}
            assert pioneer.status == "idle"
            assert (pioneer.x, pioneer.y) == (4, 2)
            assert build_update(first.id)["exploration_orders"] == []
            assert second.explored_tiles == before_second
            assert state.territory_owners == before_territory
            assert exploration.snapshot_matrix(first.id)[3][5] is not None
            assert exploration.snapshot_matrix(second.id)[3][5] is None
            assert_rejected({
                "tipo": "explorar_tile", "unit_id": pioneer.id, "x": 5, "y": 3,
            })
            assert first.recursos.gold == 480
            assert visible_positions(exploration.snapshot_matrix(first.id)) == (
                first.explored_tiles | preview_positions(first.explored_tiles)
            )
            """
        )

    def test_explore_and_claim_reject_malformed_and_unauthorized_requests(self):
        run_scenario(
            """
            pioneer = troops._new_troop(first.id, troops.PIONEER, 4, 2)
            foreign = troops._new_troop(second.id, troops.PIONEER, 4, 2)
            soldier = troops._new_troop(first.id, troops.LAND, 4, 2)
            distant = troops._new_troop(first.id, troops.PIONEER, 0, 0)
            dead = troops._new_troop(first.id, troops.PIONEER, 4, 2)
            dead.hp = 0
            for action, x, y in (("explorar_tile", 5, 2), ("reivindicar_tile", 4, 2)):
                valid = {"tipo": action, "unit_id": pioneer.id, "x": x, "y": y}
                for key in ("x", "y"):
                    for bad in (True, False, 2.5, "2", None, [], {}):
                        assert_rejected({**valid, key: bad})
                    assert_rejected({**valid, key: -1})
                    assert_rejected({**valid, key: 17})
                for bad_unit in (True, False, 1, None, [], {}, "missing"):
                    assert_rejected({**valid, "unit_id": bad_unit})
                for invalid_unit in (foreign, soldier, distant, dead):
                    assert_rejected({**valid, "unit_id": invalid_unit.id})
                # A forged payload identity cannot override connection authority.
                assert_rejected({**valid, "player_id": first.id}, second.id)
                state.phase = "lobby"
                assert_rejected(valid)
                state.phase = "game"
            """
        )

    def test_busy_pioneer_cannot_move_claim_build_or_explore_twice(self):
        run_scenario(
            """
            pioneer = troops._new_troop(first.id, troops.PIONEER, 4, 2)
            assert perform("ordenar_tropa", pioneer, 4, 4) == (None, "game")
            assert perform("explorar_tile", pioneer, 5, 2) == (None, "game")
            assert pioneer.target is None and pioneer.ordered is False
            assert exploration.is_busy(pioneer.id)
            state.territory_owners[(4, 3)] = first.id
            for data in (
                {"tipo": "ordenar_tropa", "unit_id": pioneer.id, "x": 4, "y": 4},
                {"tipo": "reivindicar_tile", "unit_id": pioneer.id, "x": 4, "y": 2},
                {"tipo": "explorar_tile", "unit_id": pioneer.id, "x": 5, "y": 3},
                {"tipo": "explorar_tile", "unit_id": pioneer.id, "x": 5, "y": 2},
                {"tipo": "construir", "tile": "city", "x, y": [4, 3]},
            ):
                assert_rejected(data)

            process_due_ticks(now=110)
            assert pioneer.status == "exploring"
            assert (pioneer.x, pioneer.y) == (4, 2)
            assert not exploration.can_build(first.id, [(4, 3)])
            # An idle second worker can still serve an adjacent construction.
            helper = troops._new_troop(first.id, troops.PIONEER, 3, 4)
            assert exploration.can_build(first.id, [(4, 3)])
            assert process_game_action(
                {"tipo": "construir", "tile": "city", "x, y": [4, 3]}, first.id,
            ) == (None, "game")
            assert pioneer.status == "exploring"
            process_due_ticks(now=120)
            assert not exploration.is_busy(pioneer.id)
            assert perform("reivindicar_tile", pioneer, 5, 2) == (None, "game")
            assert perform("ordenar_tropa", pioneer, 5, 2) == (None, "game")
            process_due_ticks(now=130)
            assert (pioneer.x, pioneer.y) == (5, 2)
            """
        )

    def test_duplicate_target_is_private_per_owner_and_does_not_double_charge(self):
        run_scenario(
            """
            pioneer = troops._new_troop(first.id, troops.PIONEER, 4, 2)
            helper = troops._new_troop(first.id, troops.PIONEER, 4, 3)
            other = troops._new_troop(second.id, troops.PIONEER, 4, 1)
            assert perform("explorar_tile", pioneer, 5, 2) == (None, "game")
            assert_rejected({
                "tipo": "explorar_tile", "unit_id": helper.id, "x": 5, "y": 2,
            })
            assert helper.status == "idle"
            assert first.recursos.gold == 480
            # Different players independently discover the same ground.
            assert perform("explorar_tile", other, 5, 2, owner=second.id) == (None, "game")
            assert first.recursos.gold == second.recursos.gold == 480
            assert {order["unit_id"] for order in build_update(first.id)["exploration_orders"]} == {pioneer.id}
            assert {order["unit_id"] for order in build_update(second.id)["exploration_orders"]} == {other.id}
            process_due_ticks(now=120)
            assert exploration.is_explored(first.id, 5, 2)
            assert exploration.is_explored(second.id, 5, 2)
            assert state.exploration_orders == {}
            """
        )

    def test_late_clock_catchup_cannot_complete_a_new_exploration_early(self):
        run_scenario(
            """
            pioneer = troops._new_troop(first.id, troops.PIONEER, 4, 2)
            known = set(first.explored_tiles)
            # The event loop has not processed any ticks despite 35 elapsed seconds.
            assert state.tick_numero == 0
            exploration.explore(first.id, pioneer.id, 5, 2, now=135)
            assert process_due_ticks(now=135) == 3
            assert first.explored_tiles == known
            assert pioneer.status == "exploring"
            assert build_update(first.id)["exploration_orders"][0]["waiting_for_start"] is True
            assert process_due_ticks(now=140) == 1
            assert first.explored_tiles == known
            assert build_update(first.id)["exploration_orders"][0]["waiting_for_start"] is False
            assert process_due_ticks(now=149.999) == 0
            assert first.explored_tiles == known
            assert process_due_ticks(now=150) == 1
            assert first.explored_tiles == known | {(5, 2)}
            assert first.recursos.gold == 480
            """
        )

    def test_death_disappearance_or_changed_origin_cancels_without_revealing(self):
        run_scenario(
            """
            known = set(first.explored_tiles)
            for cause in ("death", "removed", "moved"):
                game_clock.reset(now=100)
                pioneer = troops._new_troop(first.id, troops.PIONEER, 4, 2)
                exploration.explore(first.id, pioneer.id, 5, 2, now=105)
                if cause == "death":
                    pioneer.hp = 0
                elif cause == "removed":
                    state.troops.pop(pioneer.id)
                else:
                    pioneer.x = 3
                process_due_ticks(now=120)
                assert first.explored_tiles == known, cause
                assert state.exploration_orders == {}, cause
                assert build_update(first.id)["exploration_orders"] == []
                if cause == "moved":
                    assert pioneer.status == "idle"
            assert first.recursos.gold == 440
            """
        )

    def test_pioneer_killed_on_completion_tick_never_reveals_the_target(self):
        run_scenario(
            """
            pioneer = troops._new_troop(first.id, troops.PIONEER, 4, 2)
            enemy = troops._new_troop(second.id, troops.LAND, 4, 1)
            second.explored_tiles.update({(4, 1), (4, 2)})
            pioneer.hp = 8
            known = set(first.explored_tiles)
            assert perform("explorar_tile", pioneer, 5, 2) == (None, "game")
            process_due_ticks(now=110)
            assert pioneer.hp == 4
            assert pioneer.status == "exploring"
            assert first.explored_tiles == known
            process_due_ticks(now=120)
            assert pioneer.id not in state.troops
            assert first.explored_tiles == known
            assert state.exploration_orders == {}
            assert first.recursos.gold == 480
            """
        )

    def test_claim_requires_known_neutral_tile_and_charges_wood_and_food_once(self):
        run_scenario(
            """
            pioneer = troops._new_troop(first.id, troops.PIONEER, 4, 2)
            assert_rejected({
                "tipo": "reivindicar_tile", "unit_id": pioneer.id, "x": 5, "y": 2,
            })
            before_known = set(first.explored_tiles)
            # Claiming the tile under the pioneer is allowed.
            error, phase = perform("reivindicar_tile", pioneer, 4, 2)
            assert error is None and phase == "game"
            assert state.territory_owners[(4, 2)] == first.id
            assert first.explored_tiles == before_known
            assert first.recursos.to_dict() == {"gold": 500, "wood": 470, "food": 490}
            assert isinstance(state.matriz[2][4], tile.Grass)
            assert state.matriz[2][4].current_player is None
            assert exploration.snapshot_matrix(first.id)[2][4]["territorio"] == first.id
            assert_rejected({
                "tipo": "reivindicar_tile", "unit_id": pioneer.id, "x": 4, "y": 2,
            })
            state.territory_owners[(4, 3)] = second.id
            assert_rejected({
                "tipo": "reivindicar_tile", "unit_id": pioneer.id, "x": 4, "y": 3,
            })
            """
        )

    def test_insufficient_resources_never_partially_pay_or_change_visibility(self):
        run_scenario(
            """
            pioneer = troops._new_troop(first.id, troops.PIONEER, 4, 2)
            first.recursos.gold = 19
            assert_rejected({
                "tipo": "explorar_tile", "unit_id": pioneer.id, "x": 5, "y": 2,
            })
            first.recursos.gold = 500
            for wood, food in ((29, 500), (500, 9), (0, 0)):
                first.recursos.wood = wood
                first.recursos.food = food
                assert_rejected({
                    "tipo": "reivindicar_tile", "unit_id": pioneer.id, "x": 4, "y": 2,
                })
            """
        )

    def test_construction_requires_own_territory_and_live_adjacent_pioneer(self):
        run_scenario(
            """
            request = {"tipo": "construir", "tile": "city", "x, y": [4, 2]}
            pioneer = troops._new_troop(first.id, troops.PIONEER, 3, 2)
            # Revealed neutral ground is not owned ground.
            assert_rejected(request)
            state.territory_owners[(4, 2)] = second.id
            assert_rejected(request)
            state.territory_owners[(4, 2)] = first.id
            first.explored_tiles.remove((4, 2))
            assert_rejected(request)
            first.explored_tiles.add((4, 2))
            pioneer.x, pioneer.y = 1, 2
            assert_rejected(request)
            pioneer.x, pioneer.y = 3, 2
            pioneer.hp = 0
            assert_rejected(request)
            pioneer.hp = pioneer.max_hp
            pioneer.kind = troops.LAND
            assert_rejected(request)
            pioneer.kind = troops.PIONEER
            pioneer.x, pioneer.y = 4, 2
            assert_rejected(request)
            pioneer.x, pioneer.y = 3, 3  # Diagonal adjacency is sufficient.
            # The trusted player id still overrides the client's forged owner.
            error, phase = process_game_action({**request, "player_id": second.id}, first.id)
            assert error is None and phase == "game"
            assert isinstance(state.matriz[2][4], tile.City)
            assert state.matriz[2][4].current_player == first.id
            assert first.recursos.wood == 490
            assert second.recursos.wood == 500
            """
        )

    def test_town_center_checks_entire_footprint_and_perimeter_adjacency(self):
        run_scenario(
            """
            footprint = {(x, y) for y in range(7, 10) for x in range(7, 10)}
            first.explored_tiles.update(footprint)
            state.territory_owners.update({pos: first.id for pos in footprint})
            pioneer = troops._new_troop(first.id, troops.PIONEER, 6, 8)
            request = {"tipo": "construir", "tile": "town_center", "x, y": [8, 8]}
            corner = (9, 9)
            first.explored_tiles.remove(corner)
            assert_rejected(request)
            first.explored_tiles.add(corner)
            state.territory_owners.pop(corner)
            assert_rejected(request)
            state.territory_owners[corner] = second.id
            assert_rejected(request)
            state.territory_owners[corner] = first.id
            pioneer.x = 5
            assert_rejected(request)
            pioneer.x = 6
            error, phase = process_game_action(request, first.id)
            assert error is None and phase == "game"
            assert isinstance(state.matriz[8][8], tile.TownCenter)
            assert all(state.matriz[y][x].current_player == first.id for x, y in footprint)
            assert sum(isinstance(state.matriz[y][x], tile.City) for x, y in footprint) == 8
            """
        )

    def test_pioneer_can_cross_foreign_territory_without_revealing_more_tiles(self):
        run_scenario(
            """
            pioneer = troops._new_troop(first.id, troops.PIONEER, 0, 4)
            for x in range(5):
                state.territory_owners[(x, 4)] = second.id
            known_before = set(first.explored_tiles)
            error, phase = perform("ordenar_tropa", pioneer, 4, 4)
            assert error is None and phase == "game"
            troops.process_tick(1)
            troops.process_tick(2)
            assert (pioneer.x, pioneer.y) == (4, 4)
            assert first.explored_tiles == known_before
            assert all(state.territory_owners[(x, 4)] == second.id for x in range(5))
            assert exploration.snapshot_matrix(first.id)[4][5] == {"tile": "grass", "preview": True}
            assert_rejected({
                "tipo": "ordenar_tropa", "unit_id": pioneer.id, "x": 5, "y": 4,
            })
            """
        )

    def test_snapshots_hide_enemy_units_buildings_and_hidden_orders(self):
        run_scenario(
            """
            own = troops._new_troop(first.id, troops.PIONEER, 2, 2)
            visible_enemy = troops._new_troop(second.id, troops.LAND, 4, 2)
            hidden_enemy = troops._new_troop(second.id, troops.LAND, 12, 12)
            preview_enemy = troops._new_troop(second.id, troops.LAND, 5, 2)
            visible_enemy.target = (12, 12)
            state.matriz[12][12] = tile.GuardHouse(second.id)
            state.matriz[2][5] = tile.GuardHouse(second.id)
            state.territory_owners[(5, 2)] = second.id
            state.matriz[3][5] = tile.LumberjackCabin(second.id)
            state.matriz[3][5].base_terrain = "small_forest"
            state.matriz[4][5] = tile.Mine(second.id)
            state.matriz[5][5] = tile.Dock(second.id)
            state.matriz_dict = world.transformar_matriz_em_dict(state.matriz)
            troops.recruit(second.id, 12, 12)
            update = build_update(first.id)
            assert {unit["id"] for unit in update["troops"]} == {own.id, visible_enemy.id}
            enemy = next(unit for unit in update["troops"] if unit["id"] == visible_enemy.id)
            assert enemy.get("target") is None
            assert all((building["x"], building["y"]) != (12, 12) for building in update["command_buildings"])
            assert update["matriz"][12][12] is None
            assert exploration.snapshot_matrix(first.id)[14][14] is None
            assert hidden_enemy.id not in {unit["id"] for unit in update["troops"]}
            assert preview_enemy.id not in {unit["id"] for unit in update["troops"]}
            assert update["matriz"][2][5] == {"tile": "grass", "preview": True}
            assert update["matriz"][3][5] == {"tile": "small_forest", "preview": True}
            assert update["matriz"][4][5] == {"tile": "mountain", "preview": True}
            assert update["matriz"][5][5] == {"tile": "water", "preview": True}
            assert all(building["x"] != 5 for building in update["command_buildings"])
            """
        )

    def test_transport_sends_private_views_and_preserves_exploration_on_reconnect(self):
        run_scenario(
            """
            import asyncio
            from connections.transport import websocket_manager as transport

            async def exercise():
                first_conn, second_conn = object(), object()
                state.connections = [first_conn, second_conn]
                for conn, owner in ((first_conn, first), (second_conn, second)):
                    state.player_id_by_conn[conn] = owner.id
                    state.active_conn_by_player_id[owner.id] = conn
                    state.queues[conn] = asyncio.Queue(maxsize=4)
                    state.sent_world_revision[conn] = -1
                await transport.broadcast_game()
                for conn, owner in ((first_conn, first), (second_conn, second)):
                    message = state.queues[conn].get_nowait()
                    state.queues[conn].task_done()
                    assert known_positions(message["matriz"]) == owner.explored_tiles
                    assert visible_positions(message["matriz"]) == (
                        owner.explored_tiles | preview_positions(owner.explored_tiles)
                    )
                    state.sent_world_revision[conn] = message["world_revision"]

                pioneer = troops._new_troop(first.id, troops.PIONEER, 4, 2)
                error, phase = perform("explorar_tile", pioneer, 5, 2)
                assert error is None and phase == "game"
                # Scheduling has no map change, but its progress still broadcasts.
                await transport.broadcast_game()
                pending = state.queues[first_conn].get_nowait()
                state.queues[first_conn].task_done()
                assert pending["matriz"] is None
                assert pending["exploration_orders"][0]["unit_id"] == pioneer.id
                assert pending["exploration_orders"][0]["waiting_for_start"] is True
                pending_other = state.queues[second_conn].get_nowait()
                state.queues[second_conn].task_done()
                assert pending_other["exploration_orders"] == []
                assert process_due_ticks(now=120) == 2
                await transport.broadcast_game()
                update = state.queues[first_conn].get_nowait()
                assert update["matriz"] is not None
                assert known_positions(update["matriz"]) == first.explored_tiles
                assert len(known_positions(update["matriz"])) == 26
                other = state.queues[second_conn].get_nowait()
                if other["matriz"] is not None:
                    assert len(known_positions(other["matriz"])) == 25
                    assert other["matriz"][2][5] is None

                replacement = object()
                state.player_id_by_conn[replacement] = first.id
                state.active_conn_by_player_id[first.id] = replacement
                state.queues[replacement] = asyncio.Queue(maxsize=4)
                state.sent_world_revision[replacement] = -1
                await transport._send_game(replacement)
                resumed = state.queues[replacement].get_nowait()
                assert resumed["player_id"] == first.id
                assert known_positions(resumed["matriz"]) == first.explored_tiles
                assert resumed["recursos"]["gold"] == 480
                assert resumed["matriz"][14][14] is None

            asyncio.run(exercise())
            """
        )

    def test_lobby_restores_full_map_preview_and_game_still_has_private_fog(self):
        run_scenario(
            """
            from connections.services.lobby_runtime import build_lobby_update
            state.phase = "lobby"
            for owner in (first, second):
                update = build_lobby_update(owner.id, include_matrix=True)
                assert update["matriz"] == state.matriz_dict
                assert len(visible_positions(update["matriz"])) == 17 * 17
                assert build_lobby_update(owner.id, include_matrix=False)["matriz"] is None
            state.phase = "game"
            assert build_update(first.id)["matriz"][14][14] is None
            assert build_update(second.id)["matriz"][2][2] is None
            """
        )


if __name__ == "__main__":
    unittest.main()
