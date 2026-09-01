import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = PROJECT_ROOT / "Server"
CLIENT_DIR = PROJECT_ROOT / "Client"


def run_isolated(directory, source):
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        cwd=directory,
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


class TickRuntimeTests(unittest.TestCase):
    def test_server_clock_uses_deadlines_and_recovers_missed_ticks(self):
        run_isolated(
            SERVER_DIR,
            """
            import core.game_clock as game_clock
            import core.player as player
            import core.tile as tile
            from core.state import state
            from connections.services.game_runtime import build_update
            from connections.services.tick_event import process_due_ticks


            jogador = player.Player(
                "player-1",
                None,
                join_order=1,
                is_host=True,
            )
            mina = tile.Mine(current_player=jogador.id)
            jogador.registrar_construcao(mina, (0, 0))
            state.players = {jogador.id: jogador}
            state.phase = "game"
            state.world_revision = 7
            state.matriz_dict = [[{"tile": "mine", "dono": jogador.id}]]

            game_clock.reset(now=100.0)
            assert game_clock.snapshot(now=100.0) == {
                "match_time_ms": 0,
                "tick_interval_ms": 10_000,
                "tick_number": 0,
                "tick_remaining_ms": 10_000,
            }

            assert process_due_ticks(now=109.999) == 0
            assert state.tempo_partida == 9
            assert jogador.recursos.gold == 500
            assert game_clock.snapshot(now=109.999)["tick_remaining_ms"] == 1

            assert process_due_ticks(now=110.0) == 1
            assert state.tick_numero == 1
            assert state.tempo_partida == 10
            assert jogador.recursos.gold == 510
            assert game_clock.snapshot(now=110.0)["tick_remaining_ms"] == 10_000

            # Mesmo depois de uma pausa longa, todos os deadlines vencidos sao
            # processados sem transformar atraso do event loop em atraso de jogo.
            assert process_due_ticks(now=135.0) == 2
            assert state.tick_numero == 3
            assert state.tempo_partida == 35
            assert jogador.recursos.gold == 530
            assert game_clock.snapshot(now=135.0) == {
                "match_time_ms": 35_000,
                "tick_interval_ms": 10_000,
                "tick_number": 3,
                "tick_remaining_ms": 5_000,
            }

            update = build_update(jogador.id, include_matrix=False)
            assert update["tick_interval_ms"] == 10_000
            assert update["tick_number"] == 3
            assert 0 <= update["tick_remaining_ms"] <= 10_000
            assert update["match_time_ms"] >= 35_000
            """,
        )

    def test_client_validates_and_smoothly_advances_received_clock(self):
        run_isolated(
            CLIENT_DIR,
            """
            import connection.handlers as handlers
            import ui.api as api_module
            from core.state import state


            handlers.receber({
                "tipo": "bem_vindo",
                "player_id": "player-1",
                "is_host": True,
                "fase": "game",
            })
            handlers.time.monotonic = lambda: 100.0
            valid = {
                "tipo": "resposta",
                "fase": "game",
                "world_revision": 1,
                "matriz": [[{"tile": "grass", "dono": None}]],
                "recursos": {"gold": 500, "wood": 500, "food": 500},
                "posicao_inicial": [0, 0],
                "match_time_ms": 20_000,
                "tick_interval_ms": 10_000,
                "tick_number": 2,
                "tick_remaining_ms": 9_000,
            }
            assert handlers._aplicar_snapshot(valid) is True
            assert state.estado_jogo == "partida"

            api_module.time.monotonic = lambda: 101.25
            snapshot = api_module.GameApi().get_snapshot(-1, -1)
            assert snapshot["match_time_ms"] == 21_250
            assert snapshot["tick_interval_ms"] == 10_000
            assert snapshot["tick_number"] == 2
            assert snapshot["tick_remaining_ms"] == 7_750

            # Um relogio parcial ou fora do intervalo nao pode corromper o
            # ultimo estado completo que a interface esta exibindo.
            invalid = dict(valid)
            invalid["matriz"] = None
            invalid["recursos"] = {"gold": 999, "wood": 999, "food": 999}
            invalid.pop("tick_number")
            assert handlers._aplicar_snapshot(invalid) is False
            assert state.current_player.recursos.gold == 500
            assert state.tick_number == 2
            """,
        )


if __name__ == "__main__":
    unittest.main()
