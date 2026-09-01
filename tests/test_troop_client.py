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


class TroopClientTests(unittest.TestCase):
    def test_snapshot_reaches_the_ui_and_rejects_invalid_troops_atomically(self):
        run_isolated(
            """
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
                "world_revision": 1,
                "matriz": [[
                    {"tile": "grass", "dono": None},
                    {"tile": "water", "dono": None},
                ]],
                "recursos": {"gold": 500, "wood": 500, "food": 500},
                "posicao_inicial": [0, 0],
                "match_time_ms": 0,
                "tick_interval_ms": 10_000,
                "tick_number": 0,
                "tick_remaining_ms": 10_000,
                "troops": [{
                    "id": "troop-1",
                    "owner": "player-1",
                    "is_mine": True,
                    "kind": "land",
                    "x": 0,
                    "y": 0,
                    "hp": 12,
                    "max_hp": 12,
                    "target": [1, 0],
                    "status": "moving",
                }],
            }
            assert handlers._aplicar_snapshot(snapshot) is True
            ui_snapshot = GameApi().get_snapshot(-1, -1)
            assert ui_snapshot["player_id"] == "player-1"
            assert ui_snapshot["troops"] == snapshot["troops"]

            invalid = dict(snapshot)
            invalid["matriz"] = None
            invalid["troops"] = [dict(snapshot["troops"][0], kind="air")]
            assert handlers._aplicar_snapshot(invalid) is False
            assert state.troops == snapshot["troops"]
            """
        )

    def test_bridge_sends_valid_orders_and_exposes_military_buildings(self):
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

            assert {"guard_house", "dock"} <= session.TILES_CONSTRUCAO
            assert GameApi().command_troop("troop-7", 4, 3) == {"ok": True}
            assert sent == [{
                "tipo": "ordenar_tropa",
                "unit_id": "troop-7",
                "x": 4,
                "y": 3,
            }]

            assert session.ordenar_tropa("troop-7", True, 3) == {"ok": False}
            assert session.ordenar_tropa("troop-7", 8, 3) == {"ok": False}
            assert session.ordenar_tropa(7, 4, 3) == {"ok": False}
            assert len(sent) == 1
            """
        )


if __name__ == "__main__":
    unittest.main()
