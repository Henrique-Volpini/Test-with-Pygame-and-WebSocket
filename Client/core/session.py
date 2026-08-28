import secrets

from connection import lan_code, local_server, net
from core.generation_settings import validar_parametros_mapa
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


def hostear(tamanho=90, seed=None):
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

    if seed is None:
        seed_mundo = secrets.randbelow(2_147_483_648)
    elif isinstance(seed, bool):
        return {"ok": False}
    elif isinstance(seed, str):
        seed = seed.strip()
        if not seed.isdigit() or len(seed) > 10:
            return {"ok": False}
        seed_mundo = int(seed)
    elif isinstance(seed, int):
        seed_mundo = seed
    else:
        return {"ok": False}
    if not 0 <= seed_mundo <= 2_147_483_647:
        return {"ok": False}

    try:
        ip_host = lan_code.obter_ip_preferido()
        codigo = lan_code.criar_codigo_sala(ip_host)
    except (RuntimeError, ValueError) as exc:
        print(f"Nao foi possivel criar o codigo: {exc}")
        return {"ok": False}

    print(f"Lobby criado para mundo {tamanho_mundo}x{tamanho_mundo}")
    print(f"Codigo da partida: {codigo}")
    return {
        "ok": local_server.iniciar(
            tamanho_mundo,
            seed_mundo,
            game_code=codigo,
        ),
        "code": codigo,
    }


def conectar(codigo):
    if not isinstance(codigo, str):
        return {"ok": False}
    try:
        ip_host = lan_code.codigo_para_ip(codigo)
        uri = lan_code.criar_url_websocket(ip_host)
    except ValueError:
        return {"ok": False}
    codigo_normalizado = codigo.strip().upper()

    net.parar()
    state.resetar_sessao(
        uri,
        "Conectando ao host...",
        "connect",
        lobby_code=codigo_normalizado,
    )
    print(f"Conectando em {ip_host}...")
    net.iniciar(uri, room_code=codigo_normalizado)
    return {"ok": True}


def configurar_lobby(seed, tamanho, parametros=None):
    if (
        isinstance(seed, bool)
        or not isinstance(seed, int)
        or not 0 <= seed <= 2_147_483_647
        or isinstance(tamanho, bool)
        or not isinstance(tamanho, int)
        or not 1 <= tamanho <= 200
    ):
        return {"ok": False}
    try:
        parametros = validar_parametros_mapa(parametros)
    except ValueError:
        return {"ok": False}

    with state.lock:
        if state.estado_jogo != "lobby" or not state.lobby_is_host:
            return {"ok": False}
        state.lobby_generating = True
        state.lobby_error = None
        state.lobby_status = "Gerando uma nova prévia do mundo..."

    enviado = net.enviar(
        {
            "tipo": "configurar_lobby",
            "seed": seed,
            "tamanho": tamanho,
            "parametros_mapa": parametros,
        }
    )
    if not enviado:
        with state.lock:
            state.lobby_generating = False
            state.lobby_error = "Não foi possível enviar a configuração ao servidor."
            state.lobby_status = "Falha ao atualizar o mundo."
    return {"ok": enviado}


def regenerar_lobby(tamanho, parametros=None):
    if (
        isinstance(tamanho, bool)
        or not isinstance(tamanho, int)
        or not 1 <= tamanho <= 200
    ):
        return {"ok": False}
    try:
        parametros = validar_parametros_mapa(parametros)
    except ValueError:
        return {"ok": False}

    with state.lock:
        if state.estado_jogo != "lobby" or not state.lobby_is_host:
            return {"ok": False}
        state.lobby_generating = True
        state.lobby_error = None
        state.lobby_status = "Gerando uma nova prévia do mundo..."

    enviado = net.enviar(
        {
            "tipo": "regenerar_lobby",
            "tamanho": tamanho,
            "parametros_mapa": parametros,
        }
    )
    if not enviado:
        with state.lock:
            state.lobby_generating = False
            state.lobby_error = "Não foi possível pedir um novo mundo ao servidor."
            state.lobby_status = "Falha ao gerar outro mundo."
    return {"ok": enviado}


def iniciar_lobby():
    with state.lock:
        if (
            state.estado_jogo != "lobby"
            or not state.lobby_is_host
            or state.lobby_generating
        ):
            return {"ok": False}
    return {"ok": net.enviar({"tipo": "iniciar_partida"})}


def sair_lobby():
    with state.lock:
        session_mode = state.session_mode
    net.parar()
    if session_mode == "host":
        local_server.encerrar()
    state.voltar_ao_menu()
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
