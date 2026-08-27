import core.world as world
from core.player import Player
from core.state import state


def _marcar_partida_pronta():
    if state.player_id_criado and state.matriz_pronta:
        state.partida_criada = True
        state.iniciando_partida = False
        state.estado_jogo = "partida"


def _aplicar_snapshot(data):
    recursos = data.get("recursos")
    if not isinstance(recursos, dict):
        return False
    if not all(chave in recursos for chave in ("gold", "wood", "food")):
        return False
    if not world.atualizar_matriz(data.get("matriz")):
        return False

    with state.lock:
        state.recursos_pendentes = {
            "gold": recursos["gold"],
            "wood": recursos["wood"],
            "food": recursos["food"],
        }
        if state.current_player is not None:
            state.current_player.recursos.atualizar_recursos(state.recursos_pendentes)
        _marcar_partida_pronta()

    return True


def receber(data):
    # Esta funcao roda na thread de rede. So publica estados completos.
    if not isinstance(data, dict) or not isinstance(data.get("tipo"), str):
        print("Recebido payload com formato invalido:", data)
        return

    tipo = data["tipo"]
    if tipo in ("update", "resposta"):
        if not _aplicar_snapshot(data):
            print("Recebido snapshot com formato invalido.")
            return
        print(f"chegou {tipo}", data["recursos"])
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
            if state.recursos_pendentes is not None:
                state.current_player.recursos.atualizar_recursos(state.recursos_pendentes)
            _marcar_partida_pronta()

        print(f"Bem-vindo, jogador {player_id}!")
        return

    print("Recebido payload com tipo desconhecido:", tipo)
