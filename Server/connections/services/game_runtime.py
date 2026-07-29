import core.regras_tiles as regras_tiles
import core.world as world
from core.state import state


def process_incoming(data: dict, player_id: str):
    if state.matriz_dict is None:
        state.matriz_dict = world.criar_matriz()

    if data.get("tipo") == "construir":
        # O id confiavel e o associado a esta conexao, nao o enviado pelo cliente.
        dados_construcao = dict(data)
        dados_construcao["player_id"] = player_id
        regras_tiles.construir_em_matriz(dados_construcao)

    return {
        "tipo": "resposta",
        "matriz": state.matriz_dict,
        "recursos": state.players[player_id].recursos.to_dict(),
    }


def build_update(player_id):
    if state.matriz_dict is None:
        state.matriz_dict = world.criar_matriz()

    return {
        "tipo": "update",
        "matriz": state.matriz_dict,
        "recursos": state.players[player_id].recursos.to_dict(),
    }
