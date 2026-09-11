import asyncio

import core.game_clock as game_clock
import core.spawn as spawn
import core.troops as troops
import core.world as world
from core.state import state


LOBBY_ACTIONS = frozenset(
    {
        "configurar_lobby",
        "regenerar_lobby",
        "iniciar_partida",
    }
)


def _erro(acao, codigo, mensagem):
    return {
        "tipo": "erro",
        "acao": acao,
        "codigo": codigo,
        "mensagem": mensagem,
    }


def _jogadores_ativos():
    return sorted(
        (
            jogador
            for jogador in state.players.values()
            if jogador.id in state.active_conn_by_player_id
        ),
        key=lambda item: (item.join_order, item.id),
    )


def _jogadores_para(player_id):
    jogadores = _jogadores_ativos()
    return [
        {
            "id": jogador.id,
            "nome": "Anfitrião" if jogador.is_host else f"Jogador {jogador.join_order}",
            "is_host": jogador.is_host,
            "is_self": jogador.id == player_id,
        }
        for jogador in jogadores
    ]


def build_lobby_update(player_id, include_matrix=True):
    player = state.players.get(player_id)
    jogadores = _jogadores_para(player_id)
    host_conectado = state.host_player_id in state.active_conn_by_player_id

    if state.world_generating:
        status = "Gerando o mundo..."
    elif not host_conectado:
        status = "O anfitrião está desconectado."
    elif state.world_error:
        status = state.world_error
    else:
        status = "Mapa pronto. Aguardando o anfitrião iniciar."

    return {
        "tipo": "lobby_estado",
        "fase": state.phase,
        "revisao": state.lobby_revision,
        "world_revision": state.world_revision,
        "seed": state.world_seed,
        "largura": state.largura_grid,
        "altura": state.altura_grid,
        "parametros_mapa": dict(state.world_params),
        "composicao_mapa": dict(state.world_composition),
        "gerando": state.world_generating,
        "erro": state.world_error,
        "status": status,
        "is_host": bool(player and player.is_host),
        "host_conectado": host_conectado,
        "jogadores": jogadores,
        "matriz": state.matriz_dict if include_matrix else None,
    }


def _validar_tamanho(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 200:
        raise ValueError("O tamanho do mundo deve estar entre 1 e 200.")
    return value


def _validar_seed(value):
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not world.MIN_WORLD_SEED <= value <= world.MAX_WORLD_SEED
    ):
        raise ValueError("A seed deve estar entre 0 e 2147483647.")
    return value


async def process_lobby_action(data, player_id, broadcast):
    action = data.get("tipo")
    if action not in LOBBY_ACTIONS:
        return _erro(action, "unknown_action", "Ação de lobby desconhecida."), None
    if state.phase != "lobby":
        return _erro(action, "not_in_lobby", "A partida já foi iniciada."), None
    if player_id != state.host_player_id:
        return _erro(
            action,
            "forbidden",
            "Somente o anfitrião pode alterar ou iniciar a partida.",
        ), None
    if state.world_generating:
        return _erro(action, "world_busy", "Aguarde a geração atual terminar."), None

    if action == "iniciar_partida":
        try:
            spawn.posicionar_jogadores(
                state.matriz,
                _jogadores_ativos(),
            )
        except spawn.SpawnPlacementError as exc:
            return _erro(action, "spawn_unavailable", str(exc)), None

        state.matriz_dict = world.transformar_matriz_em_dict(state.matriz)
        state.world_revision += 1
        troops.reset()
        state.phase = "game"
        game_clock.reset()
        state.lobby_revision += 1
        return None, "game"

    try:
        tamanho = _validar_tamanho(data.get("tamanho"))
        seed = (
            world.nova_seed()
            if action == "regenerar_lobby"
            else _validar_seed(data.get("seed"))
        )
        parametros = world.validar_parametros_mapa(
            data.get("parametros_mapa", state.world_params)
        )
    except ValueError as exc:
        return _erro(action, "invalid_config", str(exc)), None

    state.world_generating = True
    state.world_error = None
    state.lobby_revision += 1
    await broadcast("lobby")

    try:
        matriz, matriz_dict = await asyncio.to_thread(
            world.gerar_mundo,
            tamanho,
            tamanho,
            seed,
            parametros,
        )
        if state.phase != "lobby":
            return _erro(action, "not_in_lobby", "A partida já foi iniciada."), None
        world.publicar_mundo(
            matriz,
            matriz_dict,
            tamanho,
            tamanho,
            seed,
            parametros,
        )
    except Exception as exc:
        state.world_error = f"Não foi possível gerar o mapa: {exc}"
    finally:
        state.world_generating = False
        state.lobby_revision += 1

    return None, "lobby"
