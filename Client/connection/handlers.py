import core.world as world

from core.state import state


def receber(data):
    # Esta funcao e chamada toda vez que chega um JSON do servidor.

    # Validar formato antes
    if data.get("tipo") is None:
        print("Recebido payload com formato invalido:", data)
        return

    if data["tipo"] == "update":
        world.atualizar_matriz(data["matriz"])

        if state.current_player is not None:
            state.current_player.recursos.atualizar_recursos(data["recursos"])

        print("chegou update", data["recursos"])

    elif data["tipo"] == "bem_vindo":
        state.player_id = data["player_id"]
        state.player_id_criado = True

        print(f"Bem-vindo, jogador {state.player_id}!")

    elif data["tipo"] == "resposta":
        world.atualizar_matriz(data["matriz"])

        if state.current_player is not None:
            state.current_player.recursos.atualizar_recursos(data["recursos"])

        print("chegou resposta", data["recursos"])

    else:
        print("Recebido payload com tipo desconhecido:", data["tipo"])
