import core.world as world
from core.player import Player
from core.state import state


def _marcar_partida_pronta():
    if (
        state.server_phase == "game"
        and state.player_id_criado
        and state.matriz_pronta
    ):
        state.partida_criada = True
        state.iniciando_partida = False
        state.estado_jogo = "partida"


def _aplicar_snapshot(data):
    if data.get("fase") != "game":
        return False

    recursos = data.get("recursos")
    if not isinstance(recursos, dict):
        return False
    if not all(chave in recursos for chave in ("gold", "wood", "food")):
        return False

    matriz = data.get("matriz")
    if matriz is not None and not world.atualizar_matriz(matriz):
        return False

    with state.lock:
        if matriz is None and not state.matriz_pronta:
            return False
        state.server_phase = "game"
        state.recursos_pendentes = {
            "gold": recursos["gold"],
            "wood": recursos["wood"],
            "food": recursos["food"],
        }
        if state.current_player is not None:
            state.current_player.recursos.atualizar_recursos(state.recursos_pendentes)
        _marcar_partida_pronta()

    return True


def _validar_jogadores(value):
    if not isinstance(value, list):
        return None

    jogadores = []
    for item in value:
        if not isinstance(item, dict):
            return None
        player_id = item.get("id")
        nome = item.get("nome")
        if not isinstance(player_id, str) or not player_id:
            return None
        if not isinstance(nome, str) or not nome:
            return None
        jogadores.append(
            {
                "id": player_id,
                "name": nome,
                "is_host": bool(item.get("is_host")),
                "is_self": bool(item.get("is_self")),
            }
        )
    return jogadores


def _aplicar_lobby(data):
    if data.get("fase") != "lobby":
        return False

    jogadores = _validar_jogadores(data.get("jogadores"))
    if jogadores is None:
        return False

    seed = data.get("seed")
    largura = data.get("largura")
    altura = data.get("altura")
    revision = data.get("revisao")
    world_revision = data.get("world_revision")
    if (
        isinstance(seed, bool)
        or not isinstance(seed, int)
        or not 0 <= seed <= 2_147_483_647
        or isinstance(largura, bool)
        or not isinstance(largura, int)
        or isinstance(altura, bool)
        or not isinstance(altura, int)
        or not 1 <= largura <= 200
        or not 1 <= altura <= 200
        or isinstance(revision, bool)
        or not isinstance(revision, int)
        or isinstance(world_revision, bool)
        or not isinstance(world_revision, int)
    ):
        return False

    matriz = data.get("matriz")
    if matriz is not None and not world.atualizar_matriz(matriz):
        return False

    with state.lock:
        if matriz is None and not state.matriz_pronta:
            return False
        state.server_phase = "lobby"
        state.estado_jogo = "lobby"
        state.iniciando_partida = False
        state.partida_criada = False
        state.lobby_revision = revision
        state.lobby_world_revision = world_revision
        state.lobby_seed = seed
        state.lobby_size = largura
        state.lobby_players = jogadores
        state.lobby_is_host = bool(data.get("is_host"))
        state.lobby_generating = bool(data.get("gerando"))
        state.lobby_status = str(data.get("status") or "")
        state.lobby_error = data.get("erro")

    return True


def receber(data):
    # Esta funcao roda na thread de rede. So publica estados completos.
    if not isinstance(data, dict) or not isinstance(data.get("tipo"), str):
        print("Recebido payload com formato invalido:", data)
        return

    tipo = data["tipo"]
    if tipo in ("update", "resposta"):
        if not _aplicar_snapshot(data):
            print("Recebido snapshot de partida com formato invalido.")
            return
        return

    if tipo == "lobby_estado":
        if not _aplicar_lobby(data):
            print("Recebido estado de lobby com formato invalido.")
        return

    if tipo == "bem_vindo":
        player_id = data.get("player_id")
        if not isinstance(player_id, str) or not player_id:
            print("Recebido payload de boas-vindas invalido.")
            return

        with state.lock:
            state.player_id = player_id
            state.player_id_criado = True
            state.current_player = Player(player_id=player_id)
            state.lobby_is_host = bool(data.get("is_host"))
            state.server_phase = data.get("fase")
            if state.recursos_pendentes is not None:
                state.current_player.recursos.atualizar_recursos(
                    state.recursos_pendentes
                )
            _marcar_partida_pronta()

        print(f"Bem-vindo, jogador {player_id}!")
        return

    if tipo == "erro":
        mensagem = str(data.get("mensagem") or "Ação recusada pelo servidor.")
        with state.lock:
            state.lobby_error = mensagem
            state.lobby_status = mensagem
            state.lobby_generating = False
        print(mensagem)
        return

    print("Recebido payload com tipo desconhecido:", tipo)
