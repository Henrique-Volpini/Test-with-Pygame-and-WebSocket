from connection import lan_code, local_server, net
from core.state import state


TILES_CONSTRUCAO = frozenset(
    {
        "grass",
        "lumberjack_cabin",
        "small_forest",
        "mountain",
        "mine",
        "town_center",
        "city",
        "water",
        "medium_forest",
        "big_forest",
    }
)


def hostear(tamanho):
    if isinstance(tamanho, bool):
        return {"ok": False}
    if isinstance(tamanho, str):
        tamanho = tamanho.strip()
        if not tamanho.isdigit() or len(tamanho) > 3:
            return {"ok": False}
    elif not isinstance(tamanho, int):
        return {"ok": False}

    tamanho_mundo = int(tamanho)
    if not 1 <= tamanho_mundo <= 200:
        print("O tamanho do mundo deve estar entre 1 e 200.")
        return {"ok": False}

    try:
        ip_host = lan_code.obter_ip_preferido()
        codigo = lan_code.ip_para_codigo(ip_host)
    except (RuntimeError, ValueError) as exc:
        print(f"Nao foi possivel criar o codigo: {exc}")
        return {"ok": False}

    print(f"Tamanho do mundo enviado: {tamanho_mundo}x{tamanho_mundo}")
    print(f"Codigo da partida: {codigo}")
    return {"ok": local_server.iniciar(tamanho_mundo), "code": codigo}


def conectar(codigo):
    if not isinstance(codigo, str):
        return {"ok": False}
    try:
        ip_host = lan_code.codigo_para_ip(codigo)
        uri = lan_code.criar_url_websocket(ip_host)
    except ValueError:
        return {"ok": False}

    net.parar()
    state.resetar_sessao(uri, "Conectando ao host...", "connect")
    print(f"Conectando em {ip_host}...")
    net.iniciar(uri)
    return {"ok": True}


def construir(x, y, nome_tile):
    if (
        isinstance(x, bool)
        or isinstance(y, bool)
        or not isinstance(x, int)
        or not isinstance(y, int)
        or not isinstance(nome_tile, str)
        or nome_tile not in TILES_CONSTRUCAO
    ):
        return {"ok": False}

    with state.lock:
        if (
            state.estado_jogo != "partida"
            or not 0 <= x < state.largura_grid
            or not 0 <= y < state.altura_grid
            or state.player_id is None
        ):
            return {"ok": False}
        player_id = state.player_id

    enviado = net.enviar(
        {
            "tipo": "construir",
            "x, y": (x, y),
            "tile": nome_tile,
            "player_id": player_id,
        }
    )
    return {"ok": enviado}
