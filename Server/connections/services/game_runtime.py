import core.game_clock as game_clock
import core.regras_tiles as regras_tiles
import core.troops as troops
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
    if action not in {"construir", "ordenar_tropa", "recrutar_tropa"}:
        return _erro(action, "unknown_action", "Ação de partida desconhecida."), None
    if state.phase != "game":
        return _erro(
            action,
            "not_in_game",
            "Não é possível executar ações antes de a partida começar.",
        ), None

    if action == "ordenar_tropa":
        try:
            troops.issue_order(
                player_id,
                data.get("unit_id"),
                data.get("x"),
                data.get("y"),
            )
        except troops.TroopActionError as exc:
            return _erro(action, exc.code, str(exc)), None
    elif action == "recrutar_tropa":
        try:
            troops.recruit(
                player_id,
                data.get("x"),
                data.get("y"),
            )
        except troops.TroopActionError as exc:
            return _erro(action, exc.code, str(exc)), None
    else:
        # O id confiavel e o associado a esta conexao, nao o enviado pelo cliente.
        dados_construcao = dict(data)
        dados_construcao["player_id"] = player_id
        if not regras_tiles.construir_em_matriz(dados_construcao):
            return _erro(
                action,
                "invalid_build",
                "Não é possível construir nesse local.",
            ), None
    return None, "game"


def build_update(player_id, include_matrix=True):
    jogador = state.players[player_id]
    update = {
        "tipo": "resposta",
        "fase": state.phase,
        "player_id": player_id,
        "world_revision": state.world_revision,
        "matriz": state.matriz_dict if include_matrix else None,
        "recursos": jogador.recursos.to_dict(),
        "posicao_inicial": (
            list(jogador.posicao_inicial)
            if jogador.posicao_inicial is not None
            else None
        ),
        "troops": troops.snapshot(player_id),
        "command_buildings": troops.command_buildings_snapshot(player_id),
        "army": troops.army_snapshot(player_id),
    }
    update.update(game_clock.snapshot())
    return update
