import core.regras_tiles as regras_tiles
from core.state import state


def _erro(acao, codigo, mensagem):
    return {
        "tipo": "erro",
        "acao": acao,
        "codigo": codigo,
        "mensagem": mensagem,
    }


def process_game_action(data: dict, player_id: str):
    action = data.get("tipo")
    if action != "construir":
        return _erro(action, "unknown_action", "Ação de partida desconhecida."), None
    if state.phase != "game":
        return _erro(
            action,
            "not_in_game",
            "Não é possível construir antes de a partida começar.",
        ), None

    # O id confiavel e o associado a esta conexao, nao o enviado pelo cliente.
    dados_construcao = dict(data)
    dados_construcao["player_id"] = player_id
    regras_tiles.construir_em_matriz(dados_construcao)
    return None, "game"


def build_update(player_id, include_matrix=True):
    return {
        "tipo": "resposta",
        "fase": state.phase,
        "world_revision": state.world_revision,
        "matriz": state.matriz_dict if include_matrix else None,
        "recursos": state.players[player_id].recursos.to_dict(),
    }
