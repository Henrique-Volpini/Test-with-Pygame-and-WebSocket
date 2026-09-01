import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = PROJECT_ROOT / "Server"


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


class InitialSpawnTests(unittest.TestCase):
    def test_one_to_four_players_receive_opposite_edge_cities_in_join_order(self):
        run_isolated(
            SERVER_DIR,
            """
            import core.spawn as spawn
            import core.tile as tile
            import core.player as player


            SIZE = 17
            INNER_MIN = spawn.SPAWN_MARGIN
            INNER_MAX = SIZE - spawn.SPAWN_MARGIN - 1
            EXPECTED_BY_JOIN_ORDER = {
                1: (INNER_MIN, INNER_MIN),
                2: (INNER_MAX, INNER_MAX),
                3: (INNER_MAX, INNER_MIN),
                4: (INNER_MIN, INNER_MAX),
            }


            def make_map():
                matrix = [
                    [tile.Mountain(current_player=None) for _ in range(SIZE)]
                    for _ in range(SIZE)
                ]
                for center_x, center_y in EXPECTED_BY_JOIN_ORDER.values():
                    for y in range(center_y - 2, center_y + 3):
                        for x in range(center_x - 2, center_x + 3):
                            matrix[y][x] = tile.Grass(current_player=None)
                return matrix


            for player_count in range(1, 5):
                matrix = make_map()
                original = [list(row) for row in matrix]
                players = [
                    player.Player(
                        f"player-{join_order}",
                        None,
                        join_order=join_order,
                        is_host=join_order == 1,
                    )
                    for join_order in range(1, player_count + 1)
                ]
                resources_before = {
                    item.id: item.recursos.to_dict()
                    for item in players
                }

                # Deliberately reverse the iterable so placement cannot depend
                # on dict/list insertion order.
                positions = spawn.posicionar_jogadores(
                    matrix,
                    reversed(players),
                )

                assert len(positions) == player_count
                assert len(set(positions.values())) == player_count

                for item in players:
                    center = EXPECTED_BY_JOIN_ORDER[item.join_order]
                    center_x, center_y = center

                    assert positions[item.id] == center
                    assert item.posicao_inicial == center
                    assert (
                        center_x in (INNER_MIN, INNER_MAX)
                        or center_y in (INNER_MIN, INNER_MAX)
                    )

                    owned_positions = set()
                    for y in range(center_y - 1, center_y + 2):
                        for x in range(center_x - 1, center_x + 2):
                            current = matrix[y][x]
                            assert current.current_player == item.id
                            if (x, y) == center:
                                assert isinstance(current, tile.TownCenter)
                            else:
                                assert isinstance(current, tile.City)
                            owned_positions.add((x, y))

                    assert len(owned_positions) == 9
                    assert len(item.construcoes) == 9
                    registered_positions = {
                        construction["pos"]
                        for construction in item.construcoes
                    }
                    assert registered_positions == owned_positions
                    for construction in item.construcoes:
                        x, y = construction["pos"]
                        assert construction["construcao"] is matrix[y][x]
                        assert construction["construcao"].current_player == item.id

                    for y in range(center_y - 2, center_y + 3):
                        for x in range(center_x - 2, center_x + 3):
                            if abs(x - center_x) <= 1 and abs(y - center_y) <= 1:
                                continue
                            current = matrix[y][x]
                            assert isinstance(current, tile.Grass)
                            assert current.current_player is None
                            assert current is original[y][x]

                    assert item.recursos.to_dict() == resources_before[item.id]
                    assert item.recursos.to_dict() == {
                        "gold": 500,
                        "wood": 500,
                        "food": 500,
                    }

                owned = {
                    position
                    for item in players
                    for position in (
                        construction["pos"]
                        for construction in item.construcoes
                    )
                }
                for y, row in enumerate(matrix):
                    for x, current in enumerate(row):
                        if (x, y) not in owned:
                            assert current is original[y][x]

                if player_count == 2:
                    first = positions["player-1"]
                    second = positions["player-2"]
                    assert first == (INNER_MIN, INNER_MIN)
                    assert second == (INNER_MAX, INNER_MAX)
                    assert first[0] + second[0] == SIZE - 1
                    assert first[1] + second[1] == SIZE - 1
            """,
        )

    def test_player_count_drives_even_distribution_beyond_four_players(self):
        run_isolated(
            SERVER_DIR,
            """
            import core.player as player
            import core.spawn as spawn
            import core.tile as tile


            size = 17
            players = [
                player.Player(f"player-{index}", None, join_order=index)
                for index in range(1, 13)
            ]
            matrix = [
                [tile.Grass(current_player=None) for _ in range(size)]
                for _ in range(size)
            ]

            positions = spawn.posicionar_jogadores(matrix, players)
            centers = [positions[item.id] for item in players]
            inner_min = spawn.SPAWN_MARGIN
            inner_max = size - spawn.SPAWN_MARGIN - 1

            assert len(set(centers)) == len(players) == 12
            for index, (center_x, center_y) in enumerate(centers):
                assert (
                    center_x in (inner_min, inner_max)
                    or center_y in (inner_min, inner_max)
                )
                assert all(
                    max(abs(center_x - other_x), abs(center_y - other_y))
                    >= spawn.MIN_CENTER_DISTANCE
                    for other_x, other_y in centers[:index]
                )
                assert len(players[index].construcoes) == 9
            """,
        )

    def test_backtracking_recovers_without_changing_unused_terrain(self):
        run_isolated(
            SERVER_DIR,
            """
            import core.player as player
            import core.spawn as spawn
            import core.tile as tile


            size = 13
            natural_centers = {(5, 5), (8, 2), (2, 8)}
            matrix = [
                [tile.Mountain(current_player=None) for _ in range(size)]
                for _ in range(size)
            ]
            for center_x, center_y in natural_centers:
                for y in range(center_y - 2, center_y + 3):
                    for x in range(center_x - 2, center_x + 3):
                        matrix[y][x] = tile.Grass(current_player=None)

            original = [list(row) for row in matrix]
            candidates = set(
                spawn._natural_grass_candidates(matrix, size, size)
            )
            assert candidates == natural_centers

            players = [
                player.Player(f"player-{index}", None, join_order=index)
                for index in range(1, 3)
            ]
            positions = spawn.posicionar_jogadores(matrix, players)

            # (5, 5) is closest to the first ideal corner, but it blocks both
            # other areas. The deterministic fallback must undo that greedy
            # choice and use the two mutually compatible natural areas.
            assert positions == {
                "player-1": (8, 2),
                "player-2": (2, 8),
            }

            changed = {
                construction["pos"]
                for item in players
                for construction in item.construcoes
            }
            assert len(changed) == 18
            for y, row in enumerate(matrix):
                for x, current in enumerate(row):
                    if (x, y) not in changed:
                        assert current is original[y][x]

            assert matrix[5][5] is original[5][5]
            assert isinstance(matrix[5][5], tile.Grass)
            assert matrix[5][5].current_player is None
            """,
        )

    def test_only_players_still_online_receive_an_initial_city(self):
        run_isolated(
            SERVER_DIR,
            """
            import asyncio

            import core.player as player
            import core.tile as tile
            import core.world as world
            from core.state import state
            from connections.services.lobby_runtime import process_lobby_action


            host = player.Player("host", None, join_order=1, is_host=True)
            disconnected = player.Player("guest", None, join_order=2)
            matrix = [
                [tile.Grass(current_player=None) for _ in range(9)]
                for _ in range(9)
            ]
            state.phase = "lobby"
            state.host_player_id = host.id
            state.players = {host.id: host, disconnected.id: disconnected}
            state.active_conn_by_player_id = {host.id: object()}
            state.matriz = matrix
            state.matriz_dict = world.transformar_matriz_em_dict(matrix)
            state.world_generating = False


            async def exercise():
                async def broadcast(_phase):
                    raise AssertionError("process_lobby_action does not broadcast directly")

                response, phase = await process_lobby_action(
                    {"tipo": "iniciar_partida"},
                    host.id,
                    broadcast,
                )
                assert response is None
                assert phase == "game"


            asyncio.run(exercise())
            assert host.posicao_inicial == (2, 2)
            assert len(host.construcoes) == 9
            assert disconnected.posicao_inicial is None
            assert disconnected.construcoes == []
            assert sum(
                cell["dono"] == host.id
                for row in state.matriz_dict
                for cell in row
            ) == 9
            assert all(
                cell["dono"] != disconnected.id
                for row in state.matriz_dict
                for cell in row
            )
            """,
        )

    def test_start_failure_is_atomic_for_tiny_and_insufficient_maps(self):
        run_isolated(
            SERVER_DIR,
            """
            import asyncio

            import core.player as player
            import core.tile as tile
            import core.world as world
            from core.state import state
            from connections.services.lobby_runtime import process_lobby_action


            async def assert_atomic_failure(
                size,
                player_count,
                terrain_type=tile.Grass,
                owned_grass=False,
            ):
                players = {
                    f"player-{join_order}": player.Player(
                        f"player-{join_order}",
                        None,
                        join_order=join_order,
                        is_host=join_order == 1,
                    )
                    for join_order in range(1, player_count + 1)
                }
                matrix = [
                    [terrain_type(current_player=None) for _ in range(size)]
                    for _ in range(size)
                ]
                if owned_grass:
                    matrix[0][0] = tile.Grass(current_player="existing-owner")
                wire = world.transformar_matriz_em_dict(matrix)

                state.phase = "lobby"
                state.host_player_id = "player-1"
                state.players = players
                state.active_conn_by_player_id = {
                    player_id: object()
                    for player_id in players
                }
                state.matriz = matrix
                state.matriz_dict = wire
                state.largura_grid = size
                state.altura_grid = size
                state.world_generating = False
                state.world_revision = 37
                state.lobby_revision = 19
                state.tempo_partida = 23

                matrix_before = world.transformar_matriz_em_dict(matrix)
                resources_before = {
                    player_id: item.recursos.to_dict()
                    for player_id, item in players.items()
                }
                broadcasts = []

                async def broadcast(phase):
                    broadcasts.append(phase)

                response, phase = await process_lobby_action(
                    {"tipo": "iniciar_partida"},
                    "player-1",
                    broadcast,
                )

                assert response["tipo"] == "erro"
                assert response["acao"] == "iniciar_partida"
                assert response["codigo"] == "spawn_unavailable"
                assert phase is None
                assert state.phase == "lobby"
                assert state.matriz is matrix
                assert state.matriz_dict is wire
                assert world.transformar_matriz_em_dict(state.matriz) == matrix_before
                assert state.world_revision == 37
                assert state.lobby_revision == 19
                assert state.tempo_partida == 23
                assert broadcasts == []

                for player_id, item in players.items():
                    assert item.posicao_inicial is None
                    assert item.construcoes == []
                    assert item.recursos.to_dict() == resources_before[player_id]


            async def exercise():
                # A 4x4 map cannot hold even one 3x3 city plus its grass ring.
                await assert_atomic_failure(size=4, player_count=1)

                # A 5x5 map has one valid center, so the second player exceeds
                # capacity. Selection must fail before placing the first city.
                await assert_atomic_failure(size=5, player_count=2)

                # Terrain is never converted to grass to manufacture a spawn.
                await assert_atomic_failure(
                    size=9,
                    player_count=1,
                    terrain_type=tile.Water,
                )

                # Even a Grass tile invalidates the area when it already has
                # an owner; the original ownership must remain untouched.
                await assert_atomic_failure(
                    size=5,
                    player_count=1,
                    owned_grass=True,
                )


            asyncio.run(exercise())
            """,
        )


if __name__ == "__main__":
    unittest.main()
