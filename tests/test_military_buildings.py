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


class MilitaryBuildingTests(unittest.TestCase):
    def test_building_cannot_delete_enemy_assets_or_terrain_under_troops(self):
        run_isolated(
            SERVER_DIR,
            """
            import core.player as player
            import core.regras_tiles as regras_tiles
            import core.tile as tile
            import core.troops as troops
            import core.world as world
            from core.state import state
            from connections.services.game_runtime import process_game_action

            owner = player.Player("owner", None, join_order=1, is_host=True)
            enemy = player.Player("enemy", None, join_order=2)
            enemy_guard = tile.GuardHouse(enemy.id)
            enemy.registrar_construcao(enemy_guard, (1, 1))
            state.players = {owner.id: owner, enemy.id: enemy}
            state.phase = "game"
            state.matriz = [
                [tile.Grass() for _ in range(3)]
                for _ in range(3)
            ]
            state.matriz[1][1] = enemy_guard
            state.matriz_dict = world.transformar_matriz_em_dict(state.matriz)
            state.world_revision = 0
            troops.reset()

            payload = {
                "tipo": "construir",
                "tile": "water",
                "x, y": [1, 1],
            }
            error, phase = process_game_action(payload, owner.id)
            assert error["codigo"] == "invalid_build" and phase is None
            assert state.matriz[1][1] is enemy_guard
            assert enemy.construcoes == [
                {"construcao": enemy_guard, "pos": (1, 1)}
            ]
            assert owner.recursos.to_dict() == {
                "gold": 500, "wood": 500, "food": 500,
            }
            assert state.world_revision == 0

            # bool nao e coordenada inteira valida, apesar de ser subtipo de
            # int em Python.
            assert regras_tiles.construir_em_matriz({
                "tile": "city",
                "x, y": [True, False],
                "player_id": owner.id,
            }) is False

            unit = troops._new_troop(owner.id, troops.LAND, 0, 0)
            assert regras_tiles.construir_em_matriz({
                "tile": "water",
                "x, y": [unit.x, unit.y],
                "player_id": owner.id,
            }) is False
            assert isinstance(state.matriz[0][0], tile.Grass)
            assert state.world_revision == 0
            """,
        )

    def test_combat_zone_blocks_free_cages_and_cache_tracks_passability_only(self):
        run_isolated(
            SERVER_DIR,
            """
            import core.player as player
            import core.tile as tile
            import core.troops as troops
            import core.world as world
            from core.state import state
            from connections.services.game_runtime import process_game_action

            builder = player.Player("builder", None, join_order=1, is_host=True)
            enemy = player.Player("enemy", None, join_order=2)
            state.players = {builder.id: builder, enemy.id: enemy}
            state.phase = "game"
            state.matriz = [[tile.Grass() for _ in range(5)] for _ in range(5)]
            state.matriz_dict = world.transformar_matriz_em_dict(state.matriz)
            state.world_revision = 0
            state.terrain_revision = 0
            troops.reset()
            troops._new_troop(enemy.id, troops.LAND, 2, 2)

            for x, y in ((2, 1), (3, 2), (2, 3), (1, 2)):
                error, phase = process_game_action(
                    {"tipo": "construir", "tile": "water", "x, y": [x, y]},
                    builder.id,
                )
                assert error["codigo"] == "invalid_build" and phase is None
                assert isinstance(state.matriz[y][x], tile.Grass)
            assert builder.recursos.gold == 500
            assert state.world_revision == state.terrain_revision == 0

            # Longe do combate, terraformar continua permitido, mas deixa de
            # ser gratuito e invalida a conectividade uma unica vez.
            error, phase = process_game_action(
                {"tipo": "construir", "tile": "water", "x, y": [0, 0]},
                builder.id,
            )
            assert error is None and phase == "game"
            assert builder.recursos.gold == 460
            assert state.world_revision == state.terrain_revision == 1
            components = troops._terrain_components(troops.LAND)

            # Grass -> City muda o snapshot visual, mas nao a passabilidade;
            # o cache de caminhos deve permanecer valido.
            error, phase = process_game_action(
                {"tipo": "construir", "tile": "city", "x, y": [4, 4]},
                builder.id,
            )
            assert error is None and phase == "game"
            assert state.world_revision == 2
            assert state.terrain_revision == 1
            assert troops._terrain_components(troops.LAND) is components
            """,
        )

    def test_guard_house_requires_a_city_owned_by_the_builder(self):
        run_isolated(
            SERVER_DIR,
            """
            import core.player as player
            import core.regras_tiles as regras_tiles
            import core.tile as tile
            import core.world as world
            from core.state import state


            dono = player.Player("owner", None, join_order=1, is_host=True)
            inimigo = player.Player("enemy", None, join_order=2)
            cidade_propria = tile.City(current_player=dono.id)
            cidade_inimiga = tile.City(current_player=inimigo.id)
            dono.registrar_construcao(cidade_propria, (1, 1))
            inimigo.registrar_construcao(cidade_inimiga, (2, 1))

            state.players = {dono.id: dono, inimigo.id: inimigo}
            state.matriz = [
                [tile.Grass(current_player=None) for _ in range(3)]
                for _ in range(3)
            ]
            state.matriz[1][1] = cidade_propria
            state.matriz[1][2] = cidade_inimiga
            state.matriz_dict = world.transformar_matriz_em_dict(state.matriz)
            state.world_revision = 0

            def construir(x, y):
                regras_tiles.construir_em_matriz({
                    "tile": "guard_house",
                    "x, y": [x, y],
                    "player_id": dono.id,
                })

            recursos_iniciais = dono.recursos.to_dict()
            construir(0, 0)
            construir(2, 1)
            assert dono.recursos.to_dict() == recursos_iniciais
            assert state.world_revision == 0
            assert isinstance(state.matriz[0][0], tile.Grass)
            assert state.matriz[1][2] is cidade_inimiga

            construir(1, 1)
            guarda = state.matriz[1][1]
            assert isinstance(guarda, tile.GuardHouse)
            assert guarda.current_player == dono.id
            assert dono.recursos.to_dict() == {
                "gold": 380,
                "wood": 320,
                "food": 420,
            }
            assert state.world_revision == 1
            assert state.matriz_dict[1][1] == {
                "tile": "guard_house",
                "dono": dono.id,
            }
            assert dono.construcoes == [{"construcao": guarda, "pos": (1, 1)}]
            assert inimigo.construcoes == [
                {"construcao": cidade_inimiga, "pos": (2, 1)}
            ]

            # Repetir sobre a propria guarda nao cobra de novo nem duplica o
            # registro: a base obrigatoria deixou de ser City.
            construir(1, 1)
            assert dono.recursos.to_dict() == {
                "gold": 380,
                "wood": 320,
                "food": 420,
            }
            assert state.world_revision == 1
            assert len(dono.construcoes) == 1
            """,
        )

    def test_dock_requires_free_coastal_water_and_cannot_chain(self):
        run_isolated(
            SERVER_DIR,
            """
            import core.player as player
            import core.regras_tiles as regras_tiles
            import core.tile as tile
            import core.world as world
            from core.state import state


            dono = player.Player("owner", None, join_order=1, is_host=True)
            inimigo = player.Player("enemy", None, join_order=2)
            state.players = {dono.id: dono, inimigo.id: inimigo}
            state.matriz = [
                [tile.Water(current_player=None) for _ in range(4)]
                for _ in range(3)
            ]
            # A unica costa inicial esta em (0, 1).
            state.matriz[1][0] = tile.Grass(current_player=None)
            state.matriz[2][0] = tile.Water(current_player=inimigo.id)
            state.matriz_dict = world.transformar_matriz_em_dict(state.matriz)
            state.world_revision = 0

            def construir(x, y):
                regras_tiles.construir_em_matriz({
                    "tile": "dock",
                    "x, y": [x, y],
                    "player_id": dono.id,
                })

            construir(1, 1)
            primeiro_dock = state.matriz[1][1]
            assert isinstance(primeiro_dock, tile.Dock)
            assert primeiro_dock.current_player == dono.id
            assert dono.recursos.to_dict() == {
                "gold": 400,
                "wood": 280,
                "food": 460,
            }
            assert state.world_revision == 1
            assert state.matriz_dict[1][1]["tile"] == "dock"

            # Um Dock nao vira costa: (2, 1) toca somente agua e o primeiro
            # Dock. O contato diagonal de (1, 0) tambem nao vale.
            construir(2, 1)
            construir(1, 0)
            # Agua pertencente ao adversario nao pode ser sobrescrita.
            construir(0, 2)
            # E a estrutura nunca pode ser erguida diretamente sobre terra.
            construir(0, 1)
            assert isinstance(state.matriz[1][2], tile.Water)
            assert isinstance(state.matriz[0][1], tile.Water)
            assert isinstance(state.matriz[2][0], tile.Water)
            assert isinstance(state.matriz[1][0], tile.Grass)
            assert dono.recursos.to_dict() == {
                "gold": 400,
                "wood": 280,
                "food": 460,
            }
            assert state.world_revision == 1
            assert dono.construcoes == [
                {"construcao": primeiro_dock, "pos": (1, 1)}
            ]

            # Agua livre na borda e ortogonalmente ao terreno continua valida.
            construir(0, 0)
            assert isinstance(state.matriz[0][0], tile.Dock)
            assert dono.recursos.to_dict() == {
                "gold": 300,
                "wood": 60,
                "food": 420,
            }
            assert state.world_revision == 2
            """,
        )

    def test_client_deserializes_the_new_buildings_and_keeps_costs_in_sync(self):
        run_isolated(
            CLIENT_DIR,
            """
            import core.tile as tile
            import core.world as world
            from core.state import state


            assert world.atualizar_matriz([[
                {"tile": "guard_house", "dono": "land-player"},
                {"tile": "dock", "dono": "naval-player"},
            ]]) is True
            assert isinstance(state.matriz[0][0], tile.GuardHouse)
            assert state.matriz[0][0].current_player == "land-player"
            assert isinstance(state.matriz[0][1], tile.Dock)
            assert state.matriz[0][1].current_player == "naval-player"

            assert (
                tile.GuardHouse.custo_gold,
                tile.GuardHouse.custo_wood,
                tile.GuardHouse.custo_food,
            ) == (120, 180, 80)
            assert (
                tile.Dock.custo_gold,
                tile.Dock.custo_wood,
                tile.Dock.custo_food,
            ) == (100, 220, 40)
            """,
        )


if __name__ == "__main__":
    unittest.main()
