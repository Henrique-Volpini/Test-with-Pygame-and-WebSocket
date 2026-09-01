import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLIENT_DIR = PROJECT_ROOT / "Client"


def run_isolated(source):
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
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


class CommandBuildingClientTests(unittest.TestCase):
    def test_snapshot_is_copied_preserved_when_absent_and_reset(self):
        run_isolated(
            """
            import copy

            import connection.handlers as handlers
            from core.state import state
            from ui.api import GameApi


            handlers.receber({
                "tipo": "bem_vindo",
                "player_id": "player-1",
                "is_host": True,
                "fase": "game",
            })
            snapshot = {
                "tipo": "resposta",
                "fase": "game",
                "player_id": "player-1",
                "matriz": [
                    [
                        {"tile": "grass", "dono": None},
                        {"tile": "grass", "dono": None},
                        {"tile": "water", "dono": None},
                        {"tile": "grass", "dono": None},
                    ],
                    [
                        {"tile": "grass", "dono": None},
                        {"tile": "grass", "dono": None},
                        {"tile": "water", "dono": None},
                        {"tile": "grass", "dono": None},
                    ],
                ],
                "recursos": {"gold": 500, "wood": 500, "food": 500},
                "posicao_inicial": [0, 0],
                "troops": [
                    {
                        "id": "troop-land-1",
                        "owner": "player-1",
                        "is_mine": True,
                        "kind": "land",
                        "x": 0,
                        "y": 1,
                        "hp": 12,
                        "max_hp": 12,
                        "target": None,
                        "status": "idle",
                    },
                    {
                        "id": "troop-land-2",
                        "owner": "player-1",
                        "is_mine": True,
                        "kind": "land",
                        "x": 1,
                        "y": 1,
                        "hp": 12,
                        "max_hp": 12,
                        "target": None,
                        "status": "idle",
                    },
                    {
                        "id": "troop-boat-1",
                        "owner": "player-1",
                        "is_mine": True,
                        "kind": "boat",
                        "x": 2,
                        "y": 1,
                        "hp": 22,
                        "max_hp": 22,
                        "target": None,
                        "status": "idle",
                    },
                ],
                "command_buildings": [
                    {
                        "x": 0,
                        "y": 0,
                        "type": "town_center",
                        "owner": "player-1",
                        "is_mine": True,
                        "queue": [],
                        "can_recruit": False,
                        "unavailable_reason": "not_recruitment_building",
                    },
                    {
                        "x": 1,
                        "y": 0,
                        "type": "guard_house",
                        "owner": "player-1",
                        "is_mine": True,
                        "queue": [{
                            "id": "queue-shared",
                            "unit_kind": "land",
                            "remaining_ticks": 2,
                            "total_ticks": 2,
                            "cost_gold": 75,
                            "waiting_for_start": True,
                        }],
                        "can_recruit": True,
                        "unavailable_reason": None,
                    },
                    {
                        "x": 2,
                        "y": 0,
                        "type": "dock",
                        "owner": "player-1",
                        "is_mine": True,
                        "queue": [{
                            "id": "queue-shared",
                            "unit_kind": "boat",
                            "remaining_ticks": 1,
                            "total_ticks": 3,
                            "cost_gold": 120,
                            "waiting_for_start": False,
                        }],
                        "can_recruit": True,
                        "unavailable_reason": None,
                    },
                    {
                        "x": 3,
                        "y": 1,
                        "type": "guard_house",
                        "owner": "player-2",
                        "is_mine": False,
                        "queue": [],
                        "can_recruit": False,
                        "unavailable_reason": "not_owner",
                    },
                ],
                "army": {
                    "land": 2,
                    "boat": 1,
                    "land_cap": 24,
                    "boat_cap": 12,
                },
            }
            expected_buildings = copy.deepcopy(snapshot["command_buildings"])
            expected_army = dict(snapshot["army"])
            assert handlers._aplicar_snapshot(snapshot) is True

            snapshot["command_buildings"][1]["queue"][0]["id"] = "changed"
            snapshot["army"]["land"] = 23
            assert state.command_buildings == expected_buildings
            assert state.army == expected_army

            api = GameApi()
            exposed = api.get_snapshot(-1, -1)
            assert exposed["command_buildings"] == expected_buildings
            assert exposed["army"] == expected_army
            exposed["command_buildings"][1]["queue"][0]["id"] = "ui-change"
            exposed["command_buildings"][1]["queue"].append({})
            exposed["army"]["boat"] = 11
            assert state.command_buildings == expected_buildings
            assert state.army == expected_army
            assert api.get_snapshot(-1, -1)["command_buildings"] == expected_buildings
            assert api.get_snapshot(-1, -1)["army"] == expected_army

            legacy_snapshot = {
                "tipo": "update",
                "fase": "game",
                "player_id": "player-1",
                "matriz": None,
                "recursos": {"gold": 450, "wood": 400, "food": 350},
                "posicao_inicial": None,
                "troops": [],
            }
            assert handlers._aplicar_snapshot(legacy_snapshot) is True
            assert state.command_buildings == expected_buildings
            assert state.army == expected_army

            state.resetar_sessao(
                "ws://127.0.0.1:8765/ws",
                "Conectando...",
                "connect",
            )
            assert state.command_buildings == []
            assert state.army == {
                "land": 0,
                "boat": 0,
                "land_cap": 24,
                "boat_cap": 12,
            }

            state.command_buildings = copy.deepcopy(expected_buildings)
            state.army = dict(expected_army)
            state.voltar_ao_menu()
            assert state.command_buildings == []
            assert state.army == {
                "land": 0,
                "boat": 0,
                "land_cap": 24,
                "boat_cap": 12,
            }
            """
        )

    def test_invalid_contract_is_rejected_before_any_publication(self):
        run_isolated(
            """
            import copy

            import connection.handlers as handlers
            from core.state import state


            def land(command_id="land-1", remaining=2, waiting=True):
                return {
                    "id": command_id,
                    "unit_kind": "land",
                    "remaining_ticks": remaining,
                    "total_ticks": 2,
                    "cost_gold": 75,
                    "waiting_for_start": waiting,
                }


            def boat(command_id="boat-1", remaining=3, waiting=True):
                return {
                    "id": command_id,
                    "unit_kind": "boat",
                    "remaining_ticks": remaining,
                    "total_ticks": 3,
                    "cost_gold": 120,
                    "waiting_for_start": waiting,
                }


            def unit(unit_id, kind, x=0):
                max_hp = 12 if kind == "land" else 22
                return {
                    "id": unit_id,
                    "owner": "player-1",
                    "is_mine": True,
                    "kind": kind,
                    "x": x,
                    "y": 0,
                    "hp": max_hp,
                    "max_hp": max_hp,
                    "target": None,
                    "status": "idle",
                }


            buildings = [
                {
                    "x": 0,
                    "y": 0,
                    "type": "town_center",
                    "owner": "player-1",
                    "is_mine": True,
                    "queue": [],
                    "can_recruit": False,
                    "unavailable_reason": "not_recruitment_building",
                },
                {
                    "x": 1,
                    "y": 0,
                    "type": "guard_house",
                    "owner": "player-1",
                    "is_mine": True,
                    "queue": [land()],
                    "can_recruit": True,
                    "unavailable_reason": None,
                },
                {
                    "x": 2,
                    "y": 0,
                    "type": "dock",
                    "owner": "player-1",
                    "is_mine": True,
                    "queue": [boat()],
                    "can_recruit": True,
                    "unavailable_reason": None,
                },
                {
                    "x": 3,
                    "y": 0,
                    "type": "guard_house",
                    "owner": "player-2",
                    "is_mine": False,
                    "queue": [],
                    "can_recruit": False,
                    "unavailable_reason": "not_owner",
                },
            ]
            army = {"land": 1, "boat": 1, "land_cap": 24, "boat_cap": 12}
            troops = [
                unit("troop-land-1", "land"),
                unit("troop-boat-1", "boat", 2),
            ]
            handlers.receber({
                "tipo": "bem_vindo",
                "player_id": "player-1",
                "is_host": True,
                "fase": "game",
            })
            initial = {
                "tipo": "resposta",
                "fase": "game",
                "player_id": "player-1",
                "matriz": [[
                    {"tile": "grass", "dono": None},
                    {"tile": "grass", "dono": None},
                    {"tile": "water", "dono": None},
                    {"tile": "grass", "dono": None},
                ]],
                "recursos": {"gold": 500, "wood": 500, "food": 500},
                "posicao_inicial": [0, 0],
                "troops": troops,
                "command_buildings": buildings,
                "army": army,
            }
            assert handlers._aplicar_snapshot(initial) is True

            five_commands = copy.deepcopy(buildings)
            five_commands[1]["queue"] = [land(f"land-{index}") for index in range(5)]
            assert handlers._validar_command_buildings(
                five_commands,
                "player-1",
                4,
                1,
            ) is not False

            queue_full_buildings = copy.deepcopy(buildings)
            queue_full_buildings[1]["queue"] = [
                land(f"full-{index}") for index in range(5)
            ]
            queue_full_buildings[1]["can_recruit"] = False
            queue_full_buildings[1]["unavailable_reason"] = "queue_full"
            assert handlers._validar_consistencia_militar(
                troops,
                queue_full_buildings,
                army,
                {"gold": 500},
            ) is True

            no_gold_buildings = copy.deepcopy(buildings)
            for building_index in (1, 2):
                no_gold_buildings[building_index]["can_recruit"] = False
                no_gold_buildings[building_index]["unavailable_reason"] = (
                    "insufficient_gold"
                )
            assert handlers._validar_consistencia_militar(
                troops,
                no_gold_buildings,
                army,
                {"gold": 0},
            ) is True

            capped_troops = [
                unit(f"cap-land-{index}", "land")
                for index in range(24)
            ] + [unit("cap-boat-1", "boat", 2)]
            capped_army = {
                "land": 24,
                "boat": 1,
                "land_cap": 24,
                "boat_cap": 12,
            }
            capped_buildings = copy.deepcopy(buildings)
            capped_buildings[1]["queue"] = []
            capped_buildings[1]["can_recruit"] = False
            capped_buildings[1]["unavailable_reason"] = "army_cap_reached"
            capped_buildings[2]["can_recruit"] = False
            capped_buildings[2]["unavailable_reason"] = "insufficient_gold"
            assert handlers._validar_consistencia_militar(
                capped_troops,
                capped_buildings,
                capped_army,
                {"gold": 0},
            ) is True

            incremental = {
                "tipo": "update",
                "fase": "game",
                "player_id": "player-1",
                "matriz": None,
                "recursos": {"gold": 999, "wood": 999, "food": 999},
                "posicao_inicial": None,
                "troops": troops,
                "command_buildings": buildings,
                "army": army,
            }

            invalid_snapshots = []

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"] = None
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["army"] = None
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            del candidate["command_buildings"][1]["queue"]
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][1]["queue"] = [
                land(f"land-{index}") for index in range(6)
            ]
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][1]["queue"] = [land(), land()]
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][1]["x"] = 4
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][1]["x"] = 0
            candidate["command_buildings"][1]["y"] = 0
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][1]["is_mine"] = False
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][1]["queue"] = [boat()]
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][2]["queue"] = [land()]
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][0]["queue"] = [land()]
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][0]["can_recruit"] = True
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][3]["can_recruit"] = True
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][3]["queue"] = [land()]
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][1]["queue"][0]["total_ticks"] = 3
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][2]["queue"][0]["cost_gold"] = 75
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][1]["queue"][0]["remaining_ticks"] = 3
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][1]["queue"][0]["remaining_ticks"] = True
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            del candidate["command_buildings"][1]["queue"][0]["waiting_for_start"]
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][1]["queue"][0]["waiting_for_start"] = "yes"
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][1]["queue"][0]["remaining_ticks"] = 1
            candidate["command_buildings"][1]["queue"][0]["waiting_for_start"] = True
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][1]["queue"] = [
                land("active-head", waiting=False),
                land("active-tail", waiting=False),
            ]
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][1]["unavailable_reason"] = "Sem ouro."
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["army"]["land"] = 2
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][1]["can_recruit"] = False
            candidate["command_buildings"][1]["unavailable_reason"] = "queue_full"
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["command_buildings"][1]["queue"] = [
                land(f"precedence-{index}") for index in range(5)
            ]
            candidate["command_buildings"][1]["can_recruit"] = False
            candidate["command_buildings"][1]["unavailable_reason"] = (
                "army_cap_reached"
            )
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["recursos"]["gold"] = 0
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["troops"] = [
                unit(f"overflow-land-{index}", "land")
                for index in range(24)
            ] + [unit("overflow-boat-1", "boat", 2)]
            candidate["army"]["land"] = 24
            candidate["command_buildings"][1]["can_recruit"] = False
            candidate["command_buildings"][1]["unavailable_reason"] = (
                "army_cap_reached"
            )
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["army"]["land_cap"] = 25
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["army"]["boat"] = 13
            invalid_snapshots.append(candidate)

            candidate = copy.deepcopy(incremental)
            candidate["army"]["land"] = True
            invalid_snapshots.append(candidate)

            before_buildings = copy.deepcopy(state.command_buildings)
            before_army = dict(state.army)
            before_resources = (
                state.current_player.recursos.gold,
                state.current_player.recursos.wood,
                state.current_player.recursos.food,
            )
            before_revision = state.world_revision
            for invalid in invalid_snapshots:
                assert handlers._aplicar_snapshot(invalid) is False
                assert state.command_buildings == before_buildings
                assert state.army == before_army
                assert (
                    state.current_player.recursos.gold,
                    state.current_player.recursos.wood,
                    state.current_player.recursos.food,
                ) == before_resources
                assert state.world_revision == before_revision
            """
        )

    def test_game_action_error_is_visible_once_per_revision_and_resets(self):
        run_isolated(
            """
            import connection.handlers as handlers
            from core.state import state
            from ui.api import GameApi


            api = GameApi()
            with state.lock:
                state.estado_jogo = "partida"

            error_payload = {
                "tipo": "erro",
                "acao": "recrutar_tropa",
                "codigo": "insufficient_gold",
                "mensagem": "Ouro insuficiente para recrutar essa tropa.",
            }
            handlers.receber(error_payload)
            expected = {
                "action": "recrutar_tropa",
                "code": "insufficient_gold",
                "message": "Ouro insuficiente para recrutar essa tropa.",
                "revision": 1,
            }
            first_poll = api.get_snapshot(-1, -1)
            second_poll = api.get_snapshot(-1, -1)
            assert first_poll["last_action_error"] == expected
            assert second_poll["last_action_error"] == expected
            assert state.last_action_error_revision == 1

            first_poll["last_action_error"]["code"] = "changed-by-ui"
            assert state.last_action_error == expected

            handlers.receber(error_payload)
            next_error = api.get_snapshot(-1, -1)["last_action_error"]
            assert next_error["revision"] == 2
            assert state.last_action_error_revision == 2

            state.resetar_sessao(
                "ws://127.0.0.1:8765/ws",
                "Conectando...",
                "connect",
            )
            assert state.last_action_error is None
            assert state.last_action_error_revision == 0
            assert api.get_snapshot(-1, -1)["last_action_error"] is None

            with state.lock:
                state.estado_jogo = "partida"
            handlers.receber(error_payload)
            assert api.get_snapshot(-1, -1)["last_action_error"]["revision"] == 1
            state.voltar_ao_menu()
            assert state.last_action_error is None
            assert state.last_action_error_revision == 0
            """
        )

    def test_recruit_bridge_validates_session_and_sends_exact_payload(self):
        run_isolated(
            """
            from connection import net
            from core import session
            from core.state import state
            from ui.api import GameApi


            sent = []
            net.enviar = lambda payload: sent.append(payload) or True
            with state.lock:
                state.estado_jogo = "partida"
                state.player_id = "player-1"
                state.largura_grid = 8
                state.altura_grid = 6

            api = GameApi()
            assert api.recruit_troop(4, 3) == {"ok": True}
            assert sent == [{
                "tipo": "recrutar_tropa",
                "x": 4,
                "y": 3,
            }]

            assert session.recrutar_tropa(True, 3) == {"ok": False}
            assert session.recrutar_tropa(4, False) == {"ok": False}
            assert session.recrutar_tropa(8, 3) == {"ok": False}
            assert session.recrutar_tropa(4, 6) == {"ok": False}
            with state.lock:
                state.estado_jogo = "lobby"
            assert session.recrutar_tropa(4, 3) == {"ok": False}
            with state.lock:
                state.estado_jogo = "partida"
                state.player_id = None
            assert session.recrutar_tropa(4, 3) == {"ok": False}
            assert len(sent) == 1

            api._shut_down = True
            assert api.recruit_troop(4, 3) == {"ok": False}
            assert len(sent) == 1
            """
        )


if __name__ == "__main__":
    unittest.main()
