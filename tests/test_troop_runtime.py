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
    return result.stdout


class TroopRuntimeTests(unittest.TestCase):
    def test_guard_and_dock_never_produce_without_manual_recruitment(self):
        run_isolated(
            """
            import core.player as player
            import core.tile as tile
            import core.troops as troops
            from core.state import state

            owner = player.Player("owner", None, 1, True)
            state.players = {owner.id: owner}
            state.matriz = [
                [
                    tile.Grass(),
                    tile.GuardHouse(owner.id),
                    tile.Grass(),
                    tile.Water(None),
                    tile.Dock(owner.id),
                    tile.Water(None),
                ],
                [
                    tile.Grass(),
                    tile.Grass(),
                    tile.Grass(),
                    tile.Water(None),
                    tile.Water(None),
                    tile.Water(None),
                ],
            ]
            troops.reset()

            for tick_number in range(1, 41):
                troops.process_tick(tick_number)
            assert state.troops == {}
            assert state.recruitment_queues == {}
            """
        )

    def test_orders_validate_authority_and_only_move_during_a_tick(self):
        run_isolated(
            """
            import core.player as player
            import core.tile as tile
            import core.troops as troops
            from core.state import state
            from connections.services.game_runtime import build_update, process_game_action

            first = player.Player("first", None, 1, True)
            second = player.Player("second", None, 2)
            state.players = {first.id: first, second.id: second}
            state.phase = "game"
            state.matriz = [
                [tile.Grass() for _ in range(6)],
                [tile.Water(None) for _ in range(6)],
            ]
            state.matriz_dict = [[{"tile": "grass", "dono": None} for _ in range(6)]]
            troops.reset()
            unit = troops._new_troop(first.id, troops.LAND, 0, 0)
            boat = troops._new_troop(first.id, troops.BOAT, 0, 1)

            error, phase = process_game_action(
                {"tipo": "ordenar_tropa", "unit_id": unit.id, "x": 5, "y": 0},
                first.id,
            )
            assert error is None and phase == "game"
            assert (unit.x, unit.y) == (0, 0)  # Ordem nao move fora do tick.
            assert unit.target == (5, 0)

            troops.process_tick(1)
            assert (unit.x, unit.y) == (2, 0)

            error, phase = process_game_action(
                {"tipo": "ordenar_tropa", "unit_id": unit.id, "x": 4, "y": 0},
                second.id,
            )
            assert error["codigo"] == "forbidden" and phase is None

            error, _ = process_game_action(
                {"tipo": "ordenar_tropa", "unit_id": unit.id, "x": 2, "y": 1},
                first.id,
            )
            assert error["codigo"] == "invalid_destination"
            error, _ = process_game_action(
                {"tipo": "ordenar_tropa", "unit_id": boat.id, "x": 2, "y": 0},
                first.id,
            )
            assert error["codigo"] == "invalid_destination"
            error, _ = process_game_action(
                {"tipo": "ordenar_tropa", "unit_id": unit.id, "x": True, "y": 0},
                first.id,
            )
            assert error["codigo"] == "invalid_destination"

            update = build_update(first.id, include_matrix=False)
            assert update["player_id"] == first.id
            assert update["troops"][0]["is_mine"] is True
            assert update["troops"][0]["target"] == [5, 0]
            """
        )

    def test_orders_use_cached_components_without_running_astar(self):
        run_isolated(
            """
            import core.player as player
            import core.tile as tile
            import core.troops as troops
            from core.state import state

            owner = player.Player("owner", None, 1, True)
            state.players = {owner.id: owner}
            state.matriz = [[tile.Grass(), tile.Water(None), tile.Grass()]]
            troops.reset()
            unit = troops._new_troop(owner.id, troops.LAND, 0, 0)

            original_find_path = troops._find_path
            troops._find_path = lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("ordem tentou calcular caminho fora do tick")
            )
            try:
                troops.issue_order(owner.id, unit.id, 2, 0)
            except troops.TroopActionError as exc:
                assert exc.code == "unreachable_destination"
            else:
                raise AssertionError("destino em outra ilha deveria ser recusado")
            assert unit.target is None

            troops.issue_order(owner.id, unit.id, 0, 0)
            assert unit.target == (0, 0)
            troops._find_path = original_find_path
            """
        )

    def test_idle_aggro_chases_and_combat_damage_is_simultaneous(self):
        run_isolated(
            """
            import core.player as player
            import core.tile as tile
            import core.troops as troops
            from core.state import state

            first = player.Player("first", None, 1, True)
            second = player.Player("second", None, 2)
            state.players = {first.id: first, second.id: second}
            state.matriz = [[tile.Grass() for _ in range(8)] for _ in range(3)]
            troops.reset()

            left = troops._new_troop(first.id, troops.LAND, 0, 1)
            right = troops._new_troop(second.id, troops.LAND, 5, 1)
            troops.process_tick(1)
            assert (left.x, left.y) == (2, 1)
            assert (right.x, right.y) != (5, 1)
            assert left.hp == right.hp == 8
            assert left.status == right.status == "attacking"

            # Com 4 HP, ambos ainda atacam e ambos morrem no mesmo ciclo.
            left.hp = right.hp = 4
            troops.process_tick(2)
            assert state.troops == {}

            # Ordem explicita tem prioridade sobre um inimigo no raio de aggro.
            ordered = troops._new_troop(first.id, troops.LAND, 0, 0)
            enemy = troops._new_troop(second.id, troops.LAND, 4, 0)
            troops.issue_order(first.id, ordered.id, 0, 2)
            troops.process_tick(3)
            assert (ordered.x, ordered.y) == (0, 2)
            assert ordered.target_unit_id is None
            assert (enemy.x, enemy.y) != (0, 2)
            """
        )

    def test_aggro_skips_unreachable_enemy_and_clears_status_after_kill(self):
        run_isolated(
            """
            import core.player as player
            import core.tile as tile
            import core.troops as troops
            from core.state import state

            first = player.Player("first", None, 1, True)
            second = player.Player("second", None, 2)
            state.players = {first.id: first, second.id: second}
            state.matriz = [
                [tile.Grass(), tile.Water(None), tile.Grass()]
                for _ in range(7)
            ]
            troops.reset()
            hunter = troops._new_troop(first.id, troops.LAND, 0, 2)
            blocked = troops._new_troop(second.id, troops.LAND, 2, 2)
            reachable = troops._new_troop(second.id, troops.LAND, 0, 6)

            troops.process_tick(1)
            assert hunter.target_unit_id == reachable.id
            assert hunter.target != (blocked.x, blocked.y)

            # Isola um duelo no qual o atacante sobrevive e mata seu alvo.
            state.troops = {}
            hunter = troops._new_troop(first.id, troops.LAND, 0, 0)
            victim = troops._new_troop(second.id, troops.LAND, 0, 1)
            victim.hp = 4
            troops.process_tick(2)
            assert victim.id not in state.troops
            assert hunter.id in state.troops
            assert hunter.target is None
            assert hunter.status == "idle"
            """
        )

    def test_missed_ticks_advance_the_manual_queue_in_order(self):
        run_isolated(
            """
            import core.game_clock as game_clock
            import core.player as player
            import core.tile as tile
            import core.troops as troops
            from core.state import state
            from connections.services.tick_event import process_due_ticks

            owner = player.Player("owner", None, 1, True)
            state.players = {owner.id: owner}
            state.phase = "game"
            state.matriz = [
                [tile.Grass(), tile.GuardHouse(owner.id), tile.Grass(), tile.Water(None)],
                [tile.Grass(), tile.Grass(), tile.Water(None), tile.Dock(owner.id)],
                [tile.Grass(), tile.Grass(), tile.Water(None), tile.Water(None)],
            ]
            troops.reset()
            troops.recruit(owner.id, 1, 0)
            troops.recruit(owner.id, 3, 1)

            game_clock.reset(now=100.0)
            assert process_due_ticks(now=130.0) == 3
            land_units = [unit for unit in state.troops.values() if unit.kind == troops.LAND]
            boats = [unit for unit in state.troops.values() if unit.kind == troops.BOAT]
            assert len(land_units) == 1
            assert (land_units[0].x, land_units[0].y) == (1, 0)
            assert boats == []
            assert state.recruitment_queues[(3, 1)][0].remaining_ticks == 1
            assert not state.recruitment_queues[(3, 1)][0].waiting_for_start

            assert process_due_ticks(now=140.0) == 1
            boats = [unit for unit in state.troops.values() if unit.kind == troops.BOAT]
            assert len(boats) == 1
            assert (boats[0].x, boats[0].y) == (3, 1)
            assert state.recruitment_queues == {}
            """
        )

    def test_new_world_resets_all_military_state(self):
        run_isolated(
            """
            import core.player as player
            import core.tile as tile
            import core.troops as troops
            import core.world as world
            from core.state import state

            owner = player.Player("owner", None, 1, True)
            state.players = {owner.id: owner}
            state.matriz = [[tile.Grass()]]
            troops.reset()
            troops._new_troop(owner.id, troops.LAND, 0, 0)
            assert state.next_troop_id == 2

            matrix = [[tile.Water(None)]]
            world.publicar_mundo(
                matrix,
                [[{"tile": "water", "dono": None}]],
                1,
                1,
                10,
                {"land": 50, "mountains": 30, "forests": 50},
            )
            assert state.troops == {}
            assert state.next_troop_id == 1
            """
        )

    def test_large_open_map_pathfinding_stays_within_tick_budget(self):
        run_isolated(
            """
            import time

            import core.player as player
            import core.tile as tile
            import core.troops as troops
            from core.state import state

            owner = player.Player("owner", None, 1, True)
            state.players = {owner.id: owner}
            state.matriz = [
                [tile.Grass() for _ in range(200)]
                for _ in range(200)
            ]
            troops.reset()
            for index in range(24):
                unit = troops._new_troop(
                    owner.id,
                    troops.LAND,
                    index % 4,
                    index // 4,
                )
                troops.issue_order(owner.id, unit.id, 199, 199)

            started = time.perf_counter()
            troops.process_tick(1)
            elapsed = time.perf_counter() - started
            # Margem ampla para maquinas lentas; a antiga BFS leva ~2,7 s na
            # maquina de referencia, enquanto o A* fica perto de 0,1 s.
            assert elapsed < 2.0, elapsed
            assert all((unit.x, unit.y) != (199, 199) for unit in state.troops.values())

            # Pior caso anterior: parede integral e alvos inalcançaveis faziam
            # duas buscas globais por unidade (~7,7 s para 24 tropas).
            state.matriz = [
                [
                    tile.Water(None) if x == 100 else tile.Grass()
                    for x in range(200)
                ]
                for _ in range(200)
            ]
            state.world_revision += 1
            troops.reset()
            for index in range(24):
                unit = troops._new_troop(
                    owner.id,
                    troops.LAND,
                    index % 4,
                    index // 4,
                )
                unit.target = (199, 199)
                unit.ordered = True

            started = time.perf_counter()
            troops.process_tick(2)
            blocked_elapsed = time.perf_counter() - started
            assert blocked_elapsed < 2.0, blocked_elapsed
            assert all(unit.target is None for unit in state.troops.values())
            """
        )


if __name__ == "__main__":
    unittest.main()
