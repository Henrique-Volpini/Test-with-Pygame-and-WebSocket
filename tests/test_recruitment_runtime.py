import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = PROJECT_ROOT / "Server"


def run_isolated(source):
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
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


class RecruitmentRuntimeTests(unittest.TestCase):
    def test_manual_cost_duration_and_per_viewer_snapshot_contract(self):
        run_isolated(
            """
            import core.player as player
            import core.tile as tile
            import core.troops as troops
            from core.state import state
            from connections.services.game_runtime import build_update, process_game_action

            owner = player.Player("owner", None, 1, True)
            enemy = player.Player("enemy", None, 2)
            state.players = {owner.id: owner, enemy.id: enemy}
            state.phase = "game"
            state.matriz = [
                [
                    tile.Grass(),
                    tile.GuardHouse(owner.id),
                    tile.Grass(),
                    tile.Water(None),
                    tile.Dock(owner.id),
                ],
                [
                    tile.Grass(),
                    tile.Grass(),
                    tile.TownCenter(owner.id),
                    tile.Water(None),
                    tile.Water(None),
                ],
            ]
            state.matriz_dict = [[{"tile": "grass", "dono": None} for _ in row] for row in state.matriz]
            troops.reset()

            # Os predios nunca mais produzem automaticamente.
            for tick in range(1, 6):
                troops.process_tick(tick)
            assert state.troops == {}

            response, phase = process_game_action(
                {
                    "tipo": "recrutar_tropa",
                    "x": 1,
                    "y": 0,
                    # Campos forjados sao ignorados; servidor infere tudo.
                    "unit_kind": "boat",
                    "cost_gold": 0,
                    "total_ticks": 0,
                },
                owner.id,
            )
            assert response is None and phase == "game"
            assert owner.recursos.gold == 425
            assert owner.recursos.wood == owner.recursos.food == 500
            response, phase = process_game_action(
                {"tipo": "recrutar_tropa", "x": 4, "y": 0},
                owner.id,
            )
            assert response is None and phase == "game"
            assert owner.recursos.gold == 305
            assert owner.recursos.wood == owner.recursos.food == 500

            snapshot = build_update(owner.id, include_matrix=False)
            assert snapshot["army"] == {
                "land": 0,
                "boat": 0,
                "land_cap": 24,
                "boat_cap": 12,
            }
            buildings = {item["type"]: item for item in snapshot["command_buildings"]}
            assert set(buildings) == {"town_center", "guard_house", "dock"}
            assert set(buildings["guard_house"]) == {
                "x", "y", "type", "owner", "is_mine", "queue",
                "can_recruit", "unavailable_reason",
            }
            assert buildings["town_center"]["queue"] == []
            assert buildings["town_center"]["can_recruit"] is False
            assert buildings["town_center"]["unavailable_reason"] == "not_recruitment_building"
            assert buildings["guard_house"]["queue"] == [{
                "id": "recruit-1",
                "unit_kind": "land",
                "remaining_ticks": 2,
                "total_ticks": 2,
                "cost_gold": 75,
                "waiting_for_start": True,
            }]
            assert buildings["dock"]["queue"] == [{
                "id": "recruit-2",
                "unit_kind": "boat",
                "remaining_ticks": 3,
                "total_ticks": 3,
                "cost_gold": 120,
                "waiting_for_start": True,
            }]

            hidden = build_update(enemy.id, include_matrix=False)["command_buildings"]
            assert all(item["queue"] == [] for item in hidden)
            assert all(item["is_mine"] is False for item in hidden)
            assert all(item["unavailable_reason"] == "not_owner" for item in hidden)

            troops.process_tick(6)
            assert state.recruitment_queues[(1, 0)][0].remaining_ticks == 2
            assert state.recruitment_queues[(4, 0)][0].remaining_ticks == 3
            assert not state.recruitment_queues[(1, 0)][0].waiting_for_start
            assert not state.recruitment_queues[(4, 0)][0].waiting_for_start
            assert state.troops == {}

            troops.process_tick(7)
            assert state.recruitment_queues[(1, 0)][0].remaining_ticks == 1
            assert state.recruitment_queues[(4, 0)][0].remaining_ticks == 2
            assert state.troops == {}

            troops.process_tick(8)
            assert sum(unit.kind == troops.LAND for unit in state.troops.values()) == 1
            assert state.recruitment_queues[(4, 0)][0].remaining_ticks == 1

            troops.process_tick(9)
            assert sum(unit.kind == troops.BOAT for unit in state.troops.values()) == 1
            assert state.recruitment_queues == {}
            assert troops.army_snapshot(owner.id) == {
                "land": 1,
                "boat": 1,
                "land_cap": 24,
                "boat_cap": 12,
            }
            """
        )

    def test_authority_queue_limit_and_strictly_serial_progress(self):
        run_isolated(
            """
            import core.player as player
            import core.tile as tile
            import core.troops as troops
            from core.state import state
            from connections.services.game_runtime import process_game_action

            owner = player.Player("owner", None, 1, True)
            enemy = player.Player("enemy", None, 2)
            owner.recursos.gold = 2_000
            state.players = {owner.id: owner, enemy.id: enemy}
            state.matriz = [[tile.GuardHouse(owner.id), tile.TownCenter(owner.id)]]
            troops.reset()

            state.phase = "lobby"
            response, phase = process_game_action(
                {"tipo": "recrutar_tropa", "x": 0, "y": 0},
                owner.id,
            )
            assert response["codigo"] == "not_in_game" and phase is None
            assert owner.recursos.gold == 2_000
            state.phase = "game"

            response, phase = process_game_action(
                {"tipo": "recrutar_tropa", "x": 0, "y": 0},
                enemy.id,
            )
            assert response["codigo"] == "not_owner" and phase is None
            assert owner.recursos.gold == 2_000
            assert enemy.recursos.gold == 500

            response, _ = process_game_action(
                {"tipo": "recrutar_tropa", "x": 1, "y": 0},
                owner.id,
            )
            assert response["codigo"] == "not_recruitment_building"
            response, _ = process_game_action(
                {"tipo": "recrutar_tropa", "x": True, "y": 0},
                owner.id,
            )
            assert response["codigo"] == "invalid_recruitment_position"

            for _ in range(5):
                response, phase = process_game_action(
                    {"tipo": "recrutar_tropa", "x": 0, "y": 0},
                    owner.id,
                )
                assert response is None and phase == "game"
            assert owner.recursos.gold == 1_625
            assert [item.id for item in state.recruitment_queues[(0, 0)]] == [
                "recruit-1", "recruit-2", "recruit-3", "recruit-4", "recruit-5"
            ]

            response, phase = process_game_action(
                {"tipo": "recrutar_tropa", "x": 0, "y": 0},
                owner.id,
            )
            assert response["codigo"] == "queue_full" and phase is None
            assert owner.recursos.gold == 1_625

            troops.process_tick(1)
            queue = state.recruitment_queues[(0, 0)]
            assert [item.remaining_ticks for item in queue] == [2, 2, 2, 2, 2]
            assert [item.waiting_for_start for item in queue] == [False, True, True, True, True]
            troops.process_tick(2)
            queue = state.recruitment_queues[(0, 0)]
            assert state.troops == {}
            assert [item.remaining_ticks for item in queue] == [1, 2, 2, 2, 2]
            troops.process_tick(3)
            queue = state.recruitment_queues[(0, 0)]
            assert len(state.troops) == 1
            assert [item.remaining_ticks for item in queue] == [2, 2, 2, 2]
            assert [item.waiting_for_start for item in queue] == [False, True, True, True]
            troops.process_tick(4)
            assert [item.remaining_ticks for item in state.recruitment_queues[(0, 0)]] == [1, 2, 2, 2]

            owner.recursos.gold = 0
            response, phase = process_game_action(
                {"tipo": "recrutar_tropa", "x": 0, "y": 0},
                owner.id,
            )
            assert response["codigo"] == "insufficient_gold" and phase is None
            assert owner.recursos.gold == 0
            """
        )

    def test_caps_include_all_live_units_and_reservations_across_buildings(self):
        run_isolated(
            """
            import core.player as player
            import core.tile as tile
            import core.troops as troops
            from core.state import state

            owner = player.Player("owner", None, 1, True)
            owner.recursos.gold = 2_000
            state.players = {owner.id: owner}
            state.matriz = [[
                tile.GuardHouse(owner.id),
                tile.GuardHouse(owner.id),
                tile.Dock(owner.id),
                tile.Dock(owner.id),
            ]]
            troops.reset()

            for index in range(19):
                troops._new_troop(owner.id, troops.LAND, 0, 0)
            for _ in range(5):
                troops.recruit(owner.id, 0, 0)
            try:
                troops.recruit(owner.id, 1, 0)
            except troops.TroopActionError as exc:
                assert exc.code == "army_cap_reached"
            else:
                raise AssertionError("reservas terrestres ultrapassaram o cap")

            for index in range(11):
                troops._new_troop(owner.id, troops.BOAT, 2, 0)
            troops.recruit(owner.id, 2, 0)
            try:
                troops.recruit(owner.id, 3, 0)
            except troops.TroopActionError as exc:
                assert exc.code == "army_cap_reached"
            else:
                raise AssertionError("reservas navais ultrapassaram o cap")

            assert troops.army_snapshot(owner.id) == {
                "land": 19,
                "boat": 11,
                "land_cap": 24,
                "boat_cap": 12,
            }
            buildings = troops.command_buildings_snapshot(owner.id)
            by_x = {item["x"]: item for item in buildings}
            assert by_x[0]["unavailable_reason"] == "queue_full"
            assert by_x[1]["unavailable_reason"] == "army_cap_reached"
            assert by_x[2]["unavailable_reason"] == "army_cap_reached"
            assert by_x[3]["unavailable_reason"] == "army_cap_reached"
            """
        )

    def test_ready_unit_waits_for_space_and_pending_queue_protects_building(self):
        run_isolated(
            """
            import core.player as player
            import core.tile as tile
            import core.troops as troops
            from core.state import state
            from connections.services.game_runtime import process_game_action

            owner = player.Player("owner", None, 1, True)
            state.players = {owner.id: owner}
            state.phase = "game"
            state.matriz = [
                [tile.Water(None), tile.Water(None), tile.Water(None)],
                [tile.Water(None), tile.GuardHouse(owner.id), tile.Water(None)],
                [tile.Water(None), tile.Water(None), tile.Water(None)],
            ]
            troops.reset()
            blockers = [
                troops._new_troop(owner.id, troops.LAND, 1, 1)
                for _ in range(4)
            ]
            troops.recruit(owner.id, 1, 1)
            troops.recruit(owner.id, 1, 1)
            assert owner.recursos.gold == 350

            troops.process_tick(1)
            troops.process_tick(2)
            troops.process_tick(3)
            queue = state.recruitment_queues[(1, 1)]
            assert [item.remaining_ticks for item in queue] == [0, 2]
            assert [item.waiting_for_start for item in queue] == [False, True]
            assert len(state.troops) == 4

            response, phase = process_game_action(
                {"tipo": "construir", "x, y": [1, 1], "tile": "grass"},
                owner.id,
            )
            assert response["codigo"] == "invalid_build" and phase is None
            assert isinstance(state.matriz[1][1], tile.GuardHouse)
            assert owner.recursos.gold == 350
            assert [item.remaining_ticks for item in state.recruitment_queues[(1, 1)]] == [0, 2]

            troops.process_tick(4)
            assert [item.remaining_ticks for item in state.recruitment_queues[(1, 1)]] == [0, 2]
            state.troops.pop(blockers[0].id)
            troops.process_tick(5)
            assert len(state.troops) == 4
            assert [item.remaining_ticks for item in state.recruitment_queues[(1, 1)]] == [2]
            assert not state.recruitment_queues[(1, 1)][0].waiting_for_start
            """
        )

    def test_catch_up_completes_each_elapsed_tick_and_resets_are_atomic(self):
        run_isolated(
            """
            import core.game_clock as game_clock
            import core.player as player
            import core.tile as tile
            import core.troops as troops
            import core.world as world
            from core.state import state
            from connections.services.tick_event import process_due_ticks

            owner = player.Player("owner", None, 1, True)
            owner.recursos.gold = 2_000
            state.players = {owner.id: owner}
            state.phase = "game"
            state.matriz = [[tile.GuardHouse(owner.id), tile.Dock(owner.id)]]
            troops.reset()

            game_clock.reset(now=100.0)
            # A ordem entra imediatamente antes do limite de 110s. Esse
            # limite apenas inicia a producao; nao e um tick ja produzido.
            assert process_due_ticks(now=109.999) == 0
            troops.recruit(owner.id, 0, 0)
            troops.recruit(owner.id, 0, 0)
            troops.recruit(owner.id, 1, 0)

            assert all(
                item.waiting_for_start
                for queue in state.recruitment_queues.values()
                for item in queue
            )
            assert process_due_ticks(now=110.0) == 1
            assert state.recruitment_queues[(0, 0)][0].remaining_ticks == 2
            assert state.recruitment_queues[(1, 0)][0].remaining_ticks == 3
            assert not state.recruitment_queues[(0, 0)][0].waiting_for_start
            assert not state.recruitment_queues[(1, 0)][0].waiting_for_start

            assert process_due_ticks(now=130.0) == 2
            assert sum(unit.kind == troops.LAND for unit in state.troops.values()) == 1
            assert sum(unit.kind == troops.BOAT for unit in state.troops.values()) == 0
            assert state.recruitment_queues[(0, 0)][0].remaining_ticks == 2
            assert state.recruitment_queues[(1, 0)][0].remaining_ticks == 1
            assert not state.recruitment_queues[(0, 0)][0].waiting_for_start

            assert process_due_ticks(now=140.0) == 1
            assert sum(unit.kind == troops.BOAT for unit in state.troops.values()) == 1
            assert (1, 0) not in state.recruitment_queues
            assert state.recruitment_queues[(0, 0)][0].remaining_ticks == 1

            assert process_due_ticks(now=150.0) == 1
            assert sum(unit.kind == troops.LAND for unit in state.troops.values()) == 2
            assert state.recruitment_queues == {}

            troops.reset()
            assert state.troops == {}
            assert state.recruitment_queues == {}
            assert state.next_troop_id == state.next_recruitment_id == 1

            troops.recruit(owner.id, 0, 0)
            assert state.recruitment_queues[(0, 0)][0].id == "recruit-1"
            matrix = [[tile.Water(None)]]
            world.publicar_mundo(
                matrix,
                [[{"tile": "water", "dono": None}]],
                1,
                1,
                55,
                {"land": 50, "mountains": 30, "forests": 50},
            )
            assert state.troops == {}
            assert state.recruitment_queues == {}
            assert state.next_troop_id == state.next_recruitment_id == 1
            """
        )


if __name__ == "__main__":
    unittest.main()
