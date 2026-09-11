import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


CLIENT_DIR = Path(__file__).resolve().parents[1] / "Client"

SCENARIO = """
import copy

import connection.handlers as handlers
from core.state import state
from ui.api import GameApi

handlers.receber({
    "tipo": "bem_vindo",
    "player_id": "first",
    "is_host": True,
    "fase": "game",
})

snapshot = {
    "tipo": "resposta",
    "fase": "game",
    "player_id": "first",
    "world_revision": 1,
    "matriz": [
        [None, {"tile": "grass", "dono": None, "territorio": "second"}, None],
        [None, {"tile": "town_center", "dono": "first", "territorio": "first"},
         {"tile": "grass", "dono": None, "territorio": None}],
        [None, None, {"tile": "small_forest", "preview": True}],
    ],
    "recursos": {"gold": 440, "wood": 500, "food": 500},
    "posicao_inicial": [1, 1],
    "troops": [{
        "id": "pioneer-1",
        "owner": "first",
        "is_mine": True,
        "kind": "pioneer",
        "x": 2,
        "y": 1,
        "hp": 10,
        "max_hp": 10,
        "target": None,
        "status": "idle",
    }],
    "command_buildings": [{
        "x": 1,
        "y": 1,
        "type": "town_center",
        "owner": "first",
        "is_mine": True,
        "queue": [{
            "id": "queue-pioneer-2",
            "unit_kind": "pioneer",
            "remaining_ticks": 1,
            "total_ticks": 1,
            "cost_gold": 60,
            "waiting_for_start": True,
        }],
        "can_recruit": True,
        "unavailable_reason": None,
    }],
    "army": {
        "land": 0, "boat": 0, "pioneer": 1,
        "land_cap": 24, "boat_cap": 12, "pioneer_cap": 8,
    },
    "exploration_rules": {
        "explore_cost": {"gold": 20, "wood": 0, "food": 0},
        "claim_cost": {"gold": 0, "wood": 30, "food": 10},
        "radius": 1,
        "total_ticks": 1,
    },
    "exploration_orders": [],
}
api = GameApi()
"""


def run_scenario(source):
    result = subprocess.run(
        [sys.executable, "-c", SCENARIO + "\n" + textwrap.dedent(source)],
        cwd=CLIENT_DIR,
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


class ExplorationClientTests(unittest.TestCase):
    def test_private_matrix_preserves_unknown_preview_and_territory_through_bridge(self):
        run_scenario(
            """
            import core.tile as tile
            assert handlers._aplicar_snapshot(snapshot) is True
            exposed = api.get_snapshot(-1, -1)
            assert exposed["screen"] == "game"
            assert exposed["matrix"] == snapshot["matriz"]
            assert exposed["matrix"][0][0] is None
            assert exposed["matrix"][0][1]["territorio"] == "second"
            assert exposed["matrix"][1][1]["territorio"] == "first"
            assert exposed["matrix"][1][2]["territorio"] is None
            assert state.matriz[0][0] is None
            assert exposed["matrix"][2][2] == {"tile": "small_forest", "preview": True}
            # A preview has a renderable terrain but is not a playable tile.
            assert state.matriz[2][2] is None
            assert isinstance(state.matriz[1][1], tile.TownCenter)
            assert state.matriz[1][1].current_player == "first"
            assert state.matriz_render == [
                [None, "grass", None], [None, "town_center", "grass"], [None, None, "small_forest"],
            ]
            revision = exposed["world_revision"]
            assert api.get_snapshot(revision, -1)["matrix"] is None

            # Territorial changes must reach the UI even if the terrain is unchanged.
            changed = copy.deepcopy(snapshot)
            changed["matriz"][1][2]["territorio"] = "first"
            assert handlers._aplicar_snapshot(changed) is True
            exposed = api.get_snapshot(revision, -1)
            assert exposed["world_revision"] > revision
            assert exposed["matrix"][1][2]["territorio"] == "first"
            assert exposed["matrix"][2][2] == {"tile": "small_forest", "preview": True}

            # Revealing the same terrain must update fog despite identical render names.
            revision = exposed["world_revision"]
            revealed = copy.deepcopy(changed)
            revealed["matriz"][2][2] = {"tile": "small_forest", "dono": None, "territorio": None}
            assert handlers._aplicar_snapshot(revealed) is True
            exposed = api.get_snapshot(revision, -1)
            assert exposed["world_revision"] > revision
            assert exposed["matrix"][2][2] == revealed["matriz"][2][2]
            assert isinstance(state.matriz[2][2], tile.SmallForest)
            """
        )

    def test_pioneer_town_center_queue_army_and_rules_reach_ui_as_copies(self):
        run_scenario(
            """
            expected = copy.deepcopy(snapshot)
            assert handlers._aplicar_snapshot(snapshot) is True
            exposed = api.get_snapshot(-1, -1)
            for key in ("troops", "command_buildings", "army", "exploration_rules", "exploration_orders"):
                assert exposed[key] == expected[key]
            assert exposed["command_buildings"][0]["can_recruit"] is True
            assert exposed["command_buildings"][0]["queue"][0]["unit_kind"] == "pioneer"
            assert exposed["army"]["pioneer"] == 1
            assert exposed["army"]["pioneer_cap"] == 8
            assert exposed["exploration_rules"]["total_ticks"] == 1

            snapshot["command_buildings"][0]["queue"][0]["id"] = "incoming-mutated"
            snapshot["army"]["pioneer"] = 8
            snapshot["exploration_rules"]["explore_cost"]["gold"] = 999
            exposed["command_buildings"][0]["queue"][0]["id"] = "ui-mutated"
            exposed["army"]["pioneer"] = 7
            exposed["exploration_rules"]["claim_cost"]["wood"] = 999
            refreshed = api.get_snapshot(-1, -1)
            for key in ("command_buildings", "army", "exploration_rules"):
                assert refreshed[key] == expected[key]

            # An incremental tick omits the matrix and retains the explored map.
            incremental = copy.deepcopy(expected)
            incremental["matriz"] = None
            incremental["command_buildings"][0]["queue"] = []
            incremental["troops"].append({**incremental["troops"][0], "id": "pioneer-2"})
            incremental["army"]["pioneer"] = 2
            assert handlers._aplicar_snapshot(incremental) is True
            assert api.get_snapshot(-1, -1)["army"]["pioneer"] == 2
            assert api.get_snapshot(-1, -1)["matrix"] == expected["matriz"]
            """
        )

    def test_invalid_territory_and_pioneer_contracts_do_not_publish_partial_state(self):
        run_scenario(
            """
            assert handlers._aplicar_snapshot(snapshot) is True
            before = api.get_snapshot(-1, -1)
            invalid = []
            for key in ("dono", "territorio"):
                for value in (True, 42, [], {}):
                    candidate = copy.deepcopy(snapshot)
                    candidate["matriz"][1][2][key] = value
                    invalid.append(candidate)
            for key in ("radius", "total_ticks"):
                for value in (True, False, 0, 2, "1", None):
                    candidate = copy.deepcopy(snapshot)
                    candidate["exploration_rules"][key] = value
                    invalid.append(candidate)
            for value in (1, "true", None, [], {}):
                candidate = copy.deepcopy(snapshot)
                candidate["matriz"][2][2]["preview"] = value
                invalid.append(candidate)
            for key in ("dono", "territorio"):
                for value in (None, "second"):
                    candidate = copy.deepcopy(snapshot)
                    candidate["matriz"][2][2][key] = value
                    invalid.append(candidate)
            for building in ("city", "town_center", "guard_house", "mine", "dock", "madeireiro"):
                candidate = copy.deepcopy(snapshot)
                candidate["matriz"][2][2]["tile"] = building
                invalid.append(candidate)
            for value in (True, -1, "20", None):
                candidate = copy.deepcopy(snapshot)
                candidate["exploration_rules"]["explore_cost"]["gold"] = value
                invalid.append(candidate)
            for key, value in (("pioneer", True), ("pioneer", 2), ("pioneer_cap", 9)):
                candidate = copy.deepcopy(snapshot)
                candidate["army"][key] = value
                invalid.append(candidate)
            candidate = copy.deepcopy(snapshot)
            candidate["command_buildings"][0]["type"] = "guard_house"
            invalid.append(candidate)
            for candidate in invalid:
                candidate["recursos"]["wood"] = 999
                assert handlers._aplicar_snapshot(candidate) is False, candidate
                after = api.get_snapshot(-1, -1)
                for key in ("matrix", "world_revision", "resources", "army", "exploration_rules", "command_buildings", "exploration_orders"):
                    assert after[key] == before[key], key
            """
        )

    def test_exploration_progress_is_copied_and_cleared_when_server_completes(self):
        run_scenario(
            """
            active = copy.deepcopy(snapshot)
            active["troops"][0]["status"] = "exploring"
            active["exploration_orders"] = [{
                "unit_id": "pioneer-1", "x": 2, "y": 2,
                "remaining_ticks": 1, "total_ticks": 1, "waiting_for_start": True,
            }]
            assert handlers._aplicar_snapshot(active) is True
            expected_orders = copy.deepcopy(active["exploration_orders"])
            exposed = api.get_snapshot(-1, -1)
            assert exposed["troops"][0]["status"] == "exploring"
            assert exposed["exploration_orders"] == expected_orders
            active["exploration_orders"][0]["x"] = 0
            exposed["exploration_orders"][0]["waiting_for_start"] = False
            assert api.get_snapshot(-1, -1)["exploration_orders"] == expected_orders

            started = copy.deepcopy(snapshot)
            started["matriz"] = None
            started["troops"][0]["status"] = "exploring"
            started["exploration_orders"] = expected_orders
            started["exploration_orders"][0]["waiting_for_start"] = False
            assert handlers._aplicar_snapshot(started) is True
            exposed = api.get_snapshot(-1, -1)
            assert exposed["exploration_orders"][0]["waiting_for_start"] is False
            assert exposed["exploration_orders"][0]["remaining_ticks"] == 1
            assert exposed["matrix"][2][2]["preview"] is True

            completed = copy.deepcopy(snapshot)
            completed["matriz"][2][2] = {"tile": "small_forest", "dono": None, "territorio": None}
            assert handlers._aplicar_snapshot(completed) is True
            exposed = api.get_snapshot(-1, -1)
            assert exposed["exploration_orders"] == []
            assert exposed["troops"][0]["status"] == "idle"
            assert exposed["matrix"][2][2] == completed["matriz"][2][2]
            """
        )

    def test_invalid_exploration_orders_do_not_publish_partial_state(self):
        run_scenario(
            """
            assert handlers._aplicar_snapshot(snapshot) is True
            before = api.get_snapshot(-1, -1)
            active = copy.deepcopy(snapshot)
            active["troops"][0]["status"] = "exploring"
            active["exploration_orders"] = [{
                "unit_id": "pioneer-1", "x": 2, "y": 2,
                "remaining_ticks": 1, "total_ticks": 1, "waiting_for_start": True,
            }]
            invalid = []
            for key, bad_values in (
                ("unit_id", (None, True, "", "missing", "a" * 65, [], {})),
                ("x", (True, -1, 3, 1.5, "2", None)),
                ("y", (True, -1, 3, 1.5, "2", None)),
                ("remaining_ticks", (True, 0, 2, "1", None)),
                ("total_ticks", (True, 0, 2, "1", None)),
                ("waiting_for_start", (None, 1, "true", [])),
            ):
                for bad_value in bad_values:
                    candidate = copy.deepcopy(active)
                    candidate["exploration_orders"][0][key] = bad_value
                    invalid.append(candidate)
            for value in (None, {}, True, "", [None], [1]):
                candidate = copy.deepcopy(active)
                candidate["exploration_orders"] = value
                invalid.append(candidate)
            candidate = copy.deepcopy(active)
            candidate["exploration_orders"] *= 2
            invalid.append(candidate)
            candidate = copy.deepcopy(active)
            candidate["exploration_orders"] = []
            invalid.append(candidate)
            for status in ("idle", "moving", "attacking", "invalid"):
                candidate = copy.deepcopy(active)
                candidate["troops"][0]["status"] = status
                invalid.append(candidate)
            candidate = copy.deepcopy(active)
            candidate["troops"][0]["owner"] = "second"
            candidate["troops"][0]["is_mine"] = False
            candidate["army"]["pioneer"] = 0
            invalid.append(candidate)
            candidate = copy.deepcopy(active)
            candidate["troops"][0]["hp"] = 0
            candidate["army"]["pioneer"] = 0
            invalid.append(candidate)
            candidate = copy.deepcopy(active)
            candidate["troops"][0]["kind"] = "land"
            candidate["army"]["pioneer"] = 0
            candidate["army"]["land"] = 1
            invalid.append(candidate)
            for candidate in invalid:
                candidate["recursos"]["wood"] = 999
                candidate["matriz"][1][2]["territorio"] = "first"
                assert handlers._aplicar_snapshot(candidate) is False, candidate
                after = api.get_snapshot(-1, -1)
                for key in ("matrix", "world_revision", "resources", "troops", "exploration_orders"):
                    assert after[key] == before[key], key
            """
        )

    def test_explore_claim_bridges_validate_input_and_only_send_authoritative_actions(self):
        run_scenario(
            """
            from connection import net
            from core import session

            assert handlers._aplicar_snapshot(snapshot) is True
            sent = []
            net.enviar = lambda payload: sent.append(payload) or True
            before = api.get_snapshot(-1, -1)
            assert api.explore_tile("pioneer-1", 2, 2) == {"ok": True}
            assert api.claim_tile("pioneer-1", 2, 1) == {"ok": True}
            assert sent == [
                {"tipo": "explorar_tile", "unit_id": "pioneer-1", "x": 2, "y": 2},
                {"tipo": "reivindicar_tile", "unit_id": "pioneer-1", "x": 2, "y": 1},
            ]
            after = api.get_snapshot(-1, -1)
            for key in ("matrix", "world_revision", "resources", "troops", "army"):
                assert after[key] == before[key], key

            for method in (api.explore_tile, api.claim_tile):
                for bad_unit in (True, 1, None, [], {}, "", "a" * 65):
                    assert method(bad_unit, 1, 1) == {"ok": False}
                for bad in (True, False, "1", 1.5, None, [], {}, -1, 3):
                    assert method("pioneer-1", bad, 1) == {"ok": False}
                    assert method("pioneer-1", 1, bad) == {"ok": False}
            assert session.acao_pioneiro("construir", "pioneer-1", 1, 1) == {"ok": False}
            assert len(sent) == 2

            state.estado_jogo = "lobby"
            assert api.explore_tile("pioneer-1", 2, 2) == {"ok": False}
            assert api.claim_tile("pioneer-1", 2, 1) == {"ok": False}
            state.estado_jogo = "partida"
            state.player_id = None
            assert api.explore_tile("pioneer-1", 2, 2) == {"ok": False}
            assert api.claim_tile("pioneer-1", 2, 1) == {"ok": False}
            state.player_id = "first"
            api._shut_down = True
            assert api.explore_tile("pioneer-1", 2, 2) == {"ok": False}
            assert api.claim_tile("pioneer-1", 2, 1) == {"ok": False}
            assert len(sent) == 2

            api._shut_down = False
            net.enviar = lambda payload: False
            assert api.explore_tile("pioneer-1", 2, 2) == {"ok": False}
            assert api.claim_tile("pioneer-1", 2, 1) == {"ok": False}
            """
        )

    def test_reset_clears_private_map_and_reconnection_restores_server_view(self):
        run_scenario(
            """
            assert handlers._aplicar_snapshot(snapshot) is True
            state.exploration_rules["explore_cost"]["gold"] = 99
            state.exploration_orders = [{"unit_id": "pioneer-1"}]
            state.resetar_sessao("ws://example/ws", "Reconectando...", "connect")
            assert state.matriz_wire is None
            assert state.matriz == []
            assert state.matriz_render == []
            assert state.troops == []
            assert state.command_buildings == []
            assert state.army["pioneer"] == 0
            assert state.army["pioneer_cap"] == 8
            assert state.exploration_rules["explore_cost"]["gold"] == 20
            assert state.exploration_rules["total_ticks"] == 1
            assert state.exploration_orders == []
            assert api.get_snapshot(-1, -1)["matrix"] is None

            handlers.receber({
                "tipo": "bem_vindo", "player_id": "first", "is_host": True, "fase": "game",
            })
            incomplete = copy.deepcopy(snapshot)
            incomplete["matriz"] = None
            assert handlers._aplicar_snapshot(incomplete) is False
            assert state.matriz_wire is None
            assert state.partida_criada is False
            restored = copy.deepcopy(snapshot)
            restored["matriz"][2][2] = {"tile": "small_forest", "dono": None, "territorio": None}
            restored["recursos"]["gold"] = 420
            assert handlers._aplicar_snapshot(restored) is True
            exposed = api.get_snapshot(-1, -1)
            assert exposed["screen"] == "game"
            assert exposed["matrix"] == restored["matriz"]
            assert exposed["matrix"][0][0] is None
            assert exposed["resources"]["gold"] == 420
            assert exposed["army"]["pioneer"] == 1

            state.exploration_orders = [{"unit_id": "pioneer-1"}]
            state.voltar_ao_menu()
            assert state.matriz_wire is None
            assert state.army["pioneer"] == 0
            assert state.command_buildings == []
            assert state.exploration_orders == []
            assert api.get_snapshot(-1, -1)["matrix"] is None
            """
        )


if __name__ == "__main__":
    unittest.main()
