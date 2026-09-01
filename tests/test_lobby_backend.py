import asyncio
import inspect
import json
import os
import socket
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


class LobbyBackendTests(unittest.TestCase):
    def test_room_and_host_headers_reject_non_ascii_without_crashing(self):
        run_isolated(
            SERVER_DIR,
            """
            from connections.transport import websocket_manager
            from core.state import state

            class FakeWebSocket:
                def __init__(self, headers):
                    self.headers = headers

            previous_room = state.room_code
            previous_host = state.host_token
            try:
                state.room_code = "ROOM9CODE"
                state.host_token = "host-token"
                malformed = FakeWebSocket({
                    websocket_manager.ROOM_CODE_HEADER: "R\u00d4OM9CODE",
                    websocket_manager.HOST_TOKEN_HEADER: "host-tok\u00e9n",
                })
                assert not websocket_manager._is_valid_room_connection(malformed)
                assert not websocket_manager._is_host_connection(malformed)
                assert not websocket_manager._secure_header_equals(
                    "\u00df", "SS", normalize=True
                )
                for invalid_code in (
                    "ROOM-CODE",
                    "ROOM_CODE",
                    "ABCDEFGHIJ",
                    "\u017f",
                ):
                    malformed.headers[websocket_manager.ROOM_CODE_HEADER] = invalid_code
                    assert not websocket_manager._is_valid_room_connection(malformed)
            finally:
                state.room_code = previous_room
                state.host_token = previous_host
            """,
        )

    def test_room_codes_change_round_trip_and_keep_legacy_compatibility(self):
        run_isolated(
            CLIENT_DIR,
            """
            from unittest.mock import patch

            from connection import lan_code
            from core import session

            ip = "26.204.139.78"
            legacy = lan_code.ip_para_codigo(ip)
            with patch(
                "connection.lan_code.secrets.randbelow",
                side_effect=[0, 0, 1],
            ):
                first = lan_code.criar_codigo_sala(ip)
                second = lan_code.criar_codigo_sala(ip)

            assert legacy == "7FORBI"
            assert len(first) == len(second) == lan_code.MAX_CODE_LENGTH == 9
            assert first != second
            assert lan_code.codigo_para_ip(first) == ip
            assert lan_code.codigo_para_ip(second) == ip
            assert lan_code.codigo_para_ip(legacy) == ip

            for invalid in (
                "",
                "ABCDEFGHIJ",
                "ABC-123",
                "+123",
                "\u017f",
                "\u00df",
            ):
                try:
                    lan_code.codigo_para_ip(invalid)
                except ValueError:
                    pass
                else:
                    raise AssertionError(f"Codigo invalido aceito: {invalid}")
            assert session.conectar("\u017f") == {"ok": False}
            assert session.conectar("\u00df") == {"ok": False}
            """,
        )

    def test_world_seed_is_deterministic_and_dimensions_are_explicit(self):
        run_isolated(
            SERVER_DIR,
            """
            from collections import Counter

            import core.world as world
            from core.generation_settings import calcular_contagens_biomas

            defaults = {"land": 50, "mountains": 50, "forests": 50}
            first_objects, first = world.gerar_mundo(13, 9, 0, defaults)
            second_objects, second = world.gerar_mundo(13, 9, 0, defaults)
            _, different = world.gerar_mundo(13, 9, 1, defaults)

            assert first == second
            assert first != different
            assert len(first_objects) == 9
            assert len(first_objects[0]) == 13
            assert len(first) == 9
            assert len(first[0]) == 13

            def composition(wire):
                raw = Counter(cell["tile"] for row in wire for cell in row)
                return {
                    "water": raw["water"],
                    "plains": raw["grass"],
                    "mountains": raw["mountain"],
                    "forests": sum(
                        raw[name]
                        for name in (
                            "small_forest",
                            "medium_forest",
                            "big_forest",
                        )
                    ),
                }

            cases = {
                "sea": {"land": 0, "mountains": 50, "forests": 50},
                "land": {"land": 100, "mountains": 50, "forests": 50},
                "mountains": {"land": 50, "mountains": 100, "forests": 50},
                "forests": {"land": 50, "mountains": 50, "forests": 100},
            }
            generated = {}
            for name, params in cases.items():
                _, wire = world.gerar_mundo(30, 20, 42, params)
                generated[name] = composition(wire)
                assert generated[name] == calcular_contagens_biomas(600, params)

            for total in range(1, 101):
                percentages = world.calcular_percentuais_biomas(total, defaults)
                assert round(sum(percentages.values()), 1) == 100.0

            assert generated["sea"]["water"] > generated["land"]["water"]
            assert generated["mountains"]["mountains"] > generated["sea"]["mountains"]
            assert generated["forests"]["forests"] > generated["sea"]["forests"]

            try:
                world.gerar_mundo(
                    10,
                    10,
                    1,
                    {"land": True, "mountains": 50, "forests": 50},
                )
            except ValueError:
                pass
            else:
                raise AssertionError("Parametro booleano foi aceito.")
            """,
        )

    def test_server_enforces_host_authority_and_lobby_phase(self):
        run_isolated(
            SERVER_DIR,
            """
            import asyncio

            import core.player as player
            import core.world as world
            from core.state import state
            from connections.services.game_runtime import process_game_action
            from connections.services.lobby_runtime import (
                build_lobby_update,
                process_lobby_action,
            )

            state.phase = "lobby"
            state.host_token = "never-publish-this-token"
            state.host_player_id = "host"
            state.players = {
                "host": player.Player("host", None, join_order=1, is_host=True),
                "guest": player.Player("guest", None, join_order=2, is_host=False),
            }
            state.active_conn_by_player_id = {
                "host": object(),
                "guest": object(),
            }
            state.world_generating = False
            state.world_error = None
            state.lobby_revision = 0
            state.world_revision = 0
            matrix, wire = world.gerar_mundo(7, 7, 10)
            world.publicar_mundo(matrix, wire, 7, 7, 10)

            async def exercise():
                broadcasts = []

                async def broadcast(phase):
                    broadcasts.append(phase)

                original_wire = state.matriz_dict
                original_revision = state.world_revision
                response, phase = await process_lobby_action(
                    {
                        "tipo": "configurar_lobby",
                        "seed": 99,
                        "tamanho": 15,
                        "parametros_mapa": {
                            "land": 90,
                            "mountains": 10,
                            "forests": 80,
                        },
                    },
                    "guest",
                    broadcast,
                )
                assert response["codigo"] == "forbidden"
                assert phase is None
                assert state.world_revision == original_revision
                assert state.matriz_dict is original_wire

                response, phase = await process_lobby_action(
                    {"tipo": "iniciar_partida"},
                    "guest",
                    broadcast,
                )
                assert response["codigo"] == "forbidden"
                assert state.phase == "lobby"

                response, phase = process_game_action(
                    {"tipo": "construir", "x, y": [0, 0], "tile": "water"},
                    "guest",
                )
                assert response["codigo"] == "not_in_game"
                assert phase is None

                response, phase = await process_lobby_action(
                    {
                        "tipo": "configurar_lobby",
                        "seed": 99,
                        "tamanho": 15,
                        "parametros_mapa": {
                            "land": 90,
                            "mountains": 10,
                            "forests": 80,
                        },
                    },
                    "host",
                    broadcast,
                )
                assert response is None
                assert phase == "lobby"
                assert state.world_seed == 99
                assert state.largura_grid == state.altura_grid == 15
                assert state.world_params == {
                    "land": 90,
                    "mountains": 10,
                    "forests": 80,
                }
                assert state.world_revision > original_revision
                preview_before_start = state.matriz_dict

                response, phase = await process_lobby_action(
                    {"tipo": "iniciar_partida"},
                    "host",
                    broadcast,
                )
                assert response is None
                assert phase == "game"
                assert state.phase == "game"
                assert state.matriz_dict is not preview_before_start
                assert sum(
                    cell["tile"] == "town_center"
                    for row in state.matriz_dict
                    for cell in row
                ) == 2
                for player_id in ("host", "guest"):
                    center_x, center_y = state.players[player_id].posicao_inicial
                    assert all(
                        preview_before_start[y][x]["tile"] == "grass"
                        for y in range(center_y - 2, center_y + 3)
                        for x in range(center_x - 2, center_x + 3)
                    )
                    assert sum(
                        state.matriz_dict[y][x]["dono"] == player_id
                        for y in range(center_y - 1, center_y + 2)
                        for x in range(center_x - 1, center_x + 2)
                    ) == 9
                assert broadcasts == ["lobby"]

            asyncio.run(exercise())

            host_snapshot = build_lobby_update("host")
            guest_snapshot = build_lobby_update("guest")
            assert host_snapshot["is_host"] is True
            assert guest_snapshot["is_host"] is False
            assert host_snapshot["parametros_mapa"] == guest_snapshot["parametros_mapa"]
            assert "never-publish-this-token" not in repr(host_snapshot)
            assert "never-publish-this-token" not in repr(guest_snapshot)
            """,
        )

    def test_client_stays_in_lobby_until_server_starts_game(self):
        run_isolated(
            CLIENT_DIR,
            """
            from connection.handlers import receber
            from core.state import state
            from ui.api import GameApi

            matrix = [
                [
                    {"tile": "grass", "dono": None},
                    {"tile": "water", "dono": None},
                ],
                [
                    {"tile": "mountain", "dono": None},
                    {"tile": "small_forest", "dono": None},
                ],
            ]

            state.voltar_ao_menu()
            state.resetar_sessao(
                "ws://example/ws",
                "Conectando...",
                "connect",
                lobby_code="ABC123",
            )
            receber({
                "tipo": "bem_vindo",
                "player_id": "guest",
                "is_host": False,
                "fase": "lobby",
            })
            receber({
                "tipo": "lobby_estado",
                "fase": "lobby",
                "revisao": 1,
                "world_revision": 4,
                "seed": 123,
                "largura": 2,
                "altura": 2,
                "gerando": False,
                "erro": None,
                "status": "Mapa pronto.",
                "is_host": False,
                "jogadores": [
                    {"id": "host", "nome": "Anfitrião", "is_host": True, "is_self": False},
                    {"id": "guest", "nome": "Jogador 2", "is_host": False, "is_self": True},
                ],
                "matriz": matrix,
            })

            assert state.estado_jogo == "lobby"
            assert state.partida_criada is False
            assert state.lobby_seed == 123
            assert len(state.lobby_players) == 2

            api = GameApi()
            first = api.get_snapshot(-1, -1)
            assert first["screen"] == "lobby"
            assert first["lobby"]["matrix"] == [
                ["grass", "water"],
                ["mountain", "small_forest"],
            ]
            cached = api.get_snapshot(-1, 4)
            assert cached["lobby"]["matrix"] is None

            receber({
                "tipo": "resposta",
                "fase": "game",
                "world_revision": 4,
                "matriz": None,
                "recursos": {"gold": 500, "wood": 500, "food": 500},
                "posicao_inicial": [1, 1],
            })
            assert state.estado_jogo == "partida"
            assert state.partida_criada is True
            assert state.spawn_position == (1, 1)
            assert api.get_snapshot(-1, -1)["spawn_position"] == [1, 1]
            """,
        )

    def test_outgoing_queue_preserves_control_messages(self):
        run_isolated(
            SERVER_DIR,
            """
            import asyncio

            from core.state import state
            from connections.transport.websocket_manager import enqueue_message

            async def exercise():
                connection = object()
                queue = asyncio.Queue(maxsize=4)
                state.queues[connection] = queue

                await enqueue_message(connection, {"tipo": "bem_vindo"})
                for revision in range(1, 6):
                    await enqueue_message(
                        connection,
                        {"tipo": "lobby_estado", "revisao": revision},
                    )

                messages = []
                while not queue.empty():
                    messages.append(queue.get_nowait())
                    queue.task_done()

                assert messages[0]["tipo"] == "bem_vindo"
                assert [item["revisao"] for item in messages[1:]] == [3, 4, 5]
                assert queue._unfinished_tasks == 0

            asyncio.run(exercise())
            """,
        )

    def test_websocket_lobby_authority_and_game_reconnection(self):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()

        environment = os.environ.copy()
        environment.update(
            {
                "TILE_GAME_WORLD_SIZE": "8",
                "TILE_GAME_WORLD_SEED": "321",
                "TILE_GAME_HOST_TOKEN": "integration-host-secret",
                "TILE_GAME_ROOM_CODE": "ROOM9CODE",
            }
        )
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=SERVER_DIR,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        try:
            for _ in range(100):
                if process.poll() is not None:
                    output = process.stdout.read() if process.stdout else ""
                    self.fail(f"Servidor encerrou durante a inicialização:\n{output}")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    if sock.connect_ex(("127.0.0.1", port)) == 0:
                        break
                finally:
                    sock.close()
                import time

                time.sleep(0.05)
            else:
                self.fail("Servidor de integração não abriu a porta a tempo.")

            async def scenario():
                import websockets

                base_url = f"ws://127.0.0.1:{port}/ws"

                async def receive(ws):
                    return json.loads(await asyncio.wait_for(ws.recv(), timeout=8))

                host_options = {"max_size": 16 * 1024 * 1024}
                header_parameter = (
                    "additional_headers"
                    if "additional_headers" in inspect.signature(
                        websockets.connect
                    ).parameters
                    else "extra_headers"
                )
                host_options[header_parameter] = {
                    "X-Tile-Game-Host": "integration-host-secret",
                    "X-Tile-Game-Player": "integration-host-player-session",
                    "X-Tile-Game-Room": "ROOM9CODE",
                }
                async with websockets.connect(base_url, **host_options) as host:
                    host_welcome = await receive(host)
                    host_player_id = host_welcome["player_id"]
                    host_lobby = await receive(host)
                    self.assertTrue(host_welcome["is_host"])
                    self.assertTrue(host_lobby["is_host"])
                    self.assertEqual(len(host_lobby["jogadores"]), 1)
                    self.assertIsNotNone(host_lobby["matriz"])

                    wrong_room_options = {"max_size": 16 * 1024 * 1024}
                    wrong_room_options[header_parameter] = {
                        "X-Tile-Game-Player": "wrong-room-player-session",
                        "X-Tile-Game-Room": "WRONGROOM",
                    }
                    async with websockets.connect(
                        base_url,
                        **wrong_room_options,
                    ) as wrong_room:
                        room_error = await receive(wrong_room)
                        self.assertEqual(room_error["codigo"], "invalid_room_code")

                    duplicate_options = {"max_size": 16 * 1024 * 1024}
                    duplicate_options[header_parameter] = {
                        "X-Tile-Game-Host": "integration-host-secret",
                        "X-Tile-Game-Player": "different-host-player-session",
                        "X-Tile-Game-Room": "ROOM9CODE",
                    }
                    async with websockets.connect(
                        base_url,
                        **duplicate_options,
                    ) as duplicate_host:
                        duplicate_error = await receive(duplicate_host)
                        self.assertEqual(
                            duplicate_error["codigo"],
                            "host_already_connected",
                        )

                    guest_options = {"max_size": 16 * 1024 * 1024}
                    guest_options[header_parameter] = {
                        "X-Tile-Game-Player": "integration-guest-player-session",
                        "X-Tile-Game-Room": "ROOM9CODE",
                    }
                    guest_player_id = None
                    async with websockets.connect(base_url, **guest_options) as guest:
                        guest_welcome = await receive(guest)
                        guest_player_id = guest_welcome["player_id"]
                        guest_lobby = await receive(guest)
                        host_roster = await receive(host)
                        self.assertFalse(guest_welcome["is_host"])
                        self.assertFalse(guest_lobby["is_host"])
                        self.assertEqual(len(guest_lobby["jogadores"]), 2)
                        self.assertEqual(len(host_roster["jogadores"]), 2)

                        await guest.send(json.dumps({"tipo": "iniciar_partida"}))
                        forbidden = await receive(guest)
                        self.assertEqual(forbidden["codigo"], "forbidden")

                        await host.send(
                            json.dumps(
                                {
                                    "tipo": "configurar_lobby",
                                    "seed": 777,
                                    "tamanho": 15,
                                    "parametros_mapa": {
                                        "land": 75,
                                        "mountains": 80,
                                        "forests": 25,
                                    },
                                }
                            )
                        )
                        host_generating = await receive(host)
                        guest_generating = await receive(guest)
                        host_generated = await receive(host)
                        guest_generated = await receive(guest)
                        self.assertTrue(host_generating["gerando"])
                        self.assertTrue(guest_generating["gerando"])
                        self.assertFalse(host_generated["gerando"])
                        self.assertEqual(host_generated["seed"], 777)
                        self.assertEqual(guest_generated["seed"], 777)
                        self.assertEqual(
                            host_generated["parametros_mapa"],
                            {
                                "land": 75,
                                "mountains": 80,
                                "forests": 25,
                            },
                        )
                        self.assertEqual(
                            host_generated["composicao_mapa"],
                            guest_generated["composicao_mapa"],
                        )
                        self.assertEqual(
                            host_generated["matriz"],
                            guest_generated["matriz"],
                        )

                        await host.send(json.dumps({"tipo": "iniciar_partida"}))
                        host_game = await receive(host)
                        guest_game = await receive(guest)
                        self.assertEqual(host_game["fase"], "game")
                        self.assertEqual(guest_game["fase"], "game")
                        for snapshot, owner in (
                            (host_game, host_player_id),
                            (guest_game, guest_player_id),
                        ):
                            center_x, center_y = snapshot["posicao_inicial"]
                            self.assertTrue(
                                all(
                                    host_generated["matriz"][y][x]["tile"]
                                    == "grass"
                                    for y in range(center_y - 2, center_y + 3)
                                    for x in range(center_x - 2, center_x + 3)
                                )
                            )
                            owned_tiles = [
                                cell
                                for row in snapshot["matriz"]
                                for cell in row
                                if cell["dono"] == owner
                            ]
                            self.assertEqual(len(owned_tiles), 9)
                            self.assertEqual(
                                sum(
                                    cell["tile"] == "town_center"
                                    for cell in owned_tiles
                                ),
                                1,
                            )

                        await guest.send(
                            json.dumps(
                                {
                                    "tipo": "construir",
                                    "x, y": [0, 0],
                                    "tile": "city",
                                }
                            )
                        )
                        host_after_build = await receive(host)
                        guest_after_build = await receive(guest)
                        self.assertEqual(host_after_build["fase"], "game")
                        self.assertEqual(
                            guest_after_build["recursos"]["wood"],
                            490,
                        )

                    async with websockets.connect(
                        base_url,
                        **guest_options,
                    ) as reconnected_guest:
                        reconnected_welcome = await receive(reconnected_guest)
                        reconnected_game = await receive(reconnected_guest)
                        self.assertEqual(
                            reconnected_welcome["player_id"],
                            guest_player_id,
                        )
                        self.assertEqual(
                            reconnected_game["recursos"]["wood"],
                            490,
                        )
                        self.assertEqual(
                            reconnected_game["matriz"][0][0]["dono"],
                            guest_player_id,
                        )

                    late_join_options = {"max_size": 16 * 1024 * 1024}
                    late_join_options[header_parameter] = {
                        "X-Tile-Game-Player": "late-guest-player-session",
                        "X-Tile-Game-Room": "ROOM9CODE",
                    }
                    async with websockets.connect(
                        base_url,
                        **late_join_options,
                    ) as late_guest:
                        late_error = await receive(late_guest)
                        self.assertEqual(
                            late_error["codigo"],
                            "game_already_started",
                        )

                    async with websockets.connect(
                        base_url,
                        **host_options,
                    ) as resumed_host:
                        resumed_welcome = await receive(resumed_host)
                        resumed_game = await receive(resumed_host)
                        self.assertEqual(
                            resumed_welcome["player_id"],
                            host_player_id,
                        )
                        self.assertTrue(resumed_welcome["is_host"])
                        self.assertEqual(resumed_game["fase"], "game")

            asyncio.run(scenario())
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            if process.stdout is not None:
                process.stdout.close()


if __name__ == "__main__":
    unittest.main()
