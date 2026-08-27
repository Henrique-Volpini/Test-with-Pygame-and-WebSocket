import asyncio
import hmac
import json
import uuid

from fastapi import WebSocket, WebSocketDisconnect

import core.player as player
from core.state import state
from connections.services.game_runtime import build_update, process_game_action
from connections.services.lobby_runtime import (
    LOBBY_ACTIONS,
    build_lobby_update,
    process_lobby_action,
)


MAX_OUTGOING_MESSAGES = 4
PLAYER_SESSION_HEADER = "x-tile-game-player"
HOST_TOKEN_HEADER = "x-tile-game-host"
SNAPSHOT_MESSAGE_TYPES = frozenset({"lobby_estado", "resposta", "update"})


def _is_snapshot_message(data):
    return data.get("tipo") in SNAPSHOT_MESSAGE_TYPES


async def enqueue_message(conn: WebSocket, data: dict):
    queue = state.queues.get(conn)
    if queue is None:
        return

    if queue.full():
        queued_messages = []
        try:
            while True:
                queued_messages.append(queue.get_nowait())
                queue.task_done()
        except asyncio.QueueEmpty:
            pass

        drop_index = next(
            (
                index
                for index, queued in enumerate(queued_messages)
                if _is_snapshot_message(queued)
            ),
            None,
        )
        if drop_index is None and not _is_snapshot_message(data):
            drop_index = next(
                (
                    index
                    for index, queued in enumerate(queued_messages)
                    if queued.get("tipo") != "bem_vindo"
                ),
                None,
            )

        if drop_index is not None:
            queued_messages.pop(drop_index)
        for queued in queued_messages:
            queue.put_nowait(queued)
        if drop_index is None:
            return
    try:
        queue.put_nowait(data)
    except asyncio.QueueFull:
        # Outro produtor ocupou a vaga no mesmo ciclo; o proximo snapshot
        # voltara a tentar e sempre carregara o estado mais recente.
        pass


async def sender_loop(conn: WebSocket, queue: asyncio.Queue):
    while True:
        data = await queue.get()
        try:
            await conn.send_json(data)
            if data.get("matriz") is not None:
                state.sent_world_revision[conn] = data.get("world_revision", -1)
        finally:
            queue.task_done()


async def _close_connection(conn, code, reason):
    try:
        await conn.close(code=code, reason=reason)
    except Exception:
        pass


def _supervise_sender(conn, task):
    if task.cancelled():
        return
    try:
        error = task.exception()
    except (asyncio.CancelledError, RuntimeError):
        return
    if error is not None:
        asyncio.create_task(
            _close_connection(conn, 1011, "Falha ao enviar atualizacao."),
        )


def _should_include_matrix(conn):
    return state.sent_world_revision.get(conn, -1) != state.world_revision


async def _send_lobby(conn):
    player_id = state.player_id_by_conn.get(conn)
    if (
        player_id not in state.players
        or state.active_conn_by_player_id.get(player_id) is not conn
    ):
        return
    include_matrix = _should_include_matrix(conn)
    await enqueue_message(
        conn,
        build_lobby_update(player_id, include_matrix=include_matrix),
    )


async def _send_game(conn):
    player_id = state.player_id_by_conn.get(conn)
    if (
        player_id not in state.players
        or state.active_conn_by_player_id.get(player_id) is not conn
    ):
        return
    include_matrix = _should_include_matrix(conn)
    await enqueue_message(
        conn,
        build_update(player_id, include_matrix=include_matrix),
    )


async def broadcast_lobby():
    for conn in list(state.connections):
        await _send_lobby(conn)


async def broadcast_game():
    for conn in list(state.connections):
        await _send_game(conn)


async def _broadcast(phase):
    if phase == "game":
        await broadcast_game()
    else:
        await broadcast_lobby()


def _player_session(websocket):
    value = websocket.headers.get(PLAYER_SESSION_HEADER)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if 16 <= len(value) <= 256 else None


def _is_host_connection(websocket, existing_player_id=None):
    provided_token = websocket.headers.get(HOST_TOKEN_HEADER)
    if state.host_token:
        return bool(provided_token) and hmac.compare_digest(
            provided_token,
            state.host_token,
        )
    if existing_player_id == state.host_player_id:
        return True
    return state.host_player_id is None


def _connection_identity(websocket):
    session_token = _player_session(websocket)
    player_id = (
        state.player_id_by_session.get(session_token)
        if session_token is not None
        else None
    )
    jogador = state.players.get(player_id)
    if player_id is not None and jogador is None:
        state.player_id_by_session.pop(session_token, None)
        player_id = None

    is_host = _is_host_connection(websocket, player_id)
    if jogador is not None and jogador.is_host and not is_host:
        return None, {
            "tipo": "erro",
            "codigo": "invalid_host_session",
            "mensagem": "A credencial do anfitriao nao foi apresentada.",
        }

    current_host_id = state.host_player_id
    if is_host and current_host_id is not None and current_host_id != player_id:
        current_host = state.players.get(current_host_id)
        current_host_conn = state.active_conn_by_player_id.get(current_host_id)
        if current_host_conn is not None:
            return None, {
                "tipo": "erro",
                "codigo": "host_already_connected",
                "mensagem": "O anfitriao ja esta conectado por outra sessao.",
            }
        if jogador is not None:
            return None, {
                "tipo": "erro",
                "codigo": "player_session_conflict",
                "mensagem": "A sessao informada pertence a outro jogador.",
            }
        if current_host is not None:
            player_id = current_host_id
            jogador = current_host

    if jogador is None and state.phase == "game":
        return None, {
            "tipo": "erro",
            "codigo": "game_already_started",
            "mensagem": "A partida ja comecou e nao aceita novos jogadores.",
        }

    if jogador is None:
        player_id = str(uuid.uuid4())
        jogador = player.Player(
            player_id,
            websocket,
            join_order=state.next_player_order,
            is_host=is_host,
        )
        state.next_player_order += 1
        state.players[player_id] = jogador
    else:
        jogador.controller = websocket
        if is_host:
            jogador.is_host = True

    if jogador.is_host:
        state.host_player_id = player_id

    if session_token is not None:
        old_session = state.player_session_by_id.get(player_id)
        if (
            old_session is not None
            and old_session != session_token
            and state.player_id_by_session.get(old_session) == player_id
        ):
            state.player_id_by_session.pop(old_session, None)
        state.player_id_by_session[session_token] = player_id
        state.player_session_by_id[player_id] = session_token

    return (player_id, jogador, session_token), None


async def websocket_handler(websocket: WebSocket):
    await websocket.accept()
    identity, identity_error = _connection_identity(websocket)
    if identity_error is not None:
        await websocket.send_json(identity_error)
        await _close_connection(websocket, 1008, identity_error["codigo"])
        return

    player_id, jogador, _session_token = identity
    replaced_connection = state.active_conn_by_player_id.get(player_id)

    state.connections.append(websocket)
    state.player_id_by_conn[websocket] = player_id
    state.active_conn_by_player_id[player_id] = websocket

    queue = asyncio.Queue(maxsize=MAX_OUTGOING_MESSAGES)
    state.queues[websocket] = queue
    state.sent_world_revision[websocket] = -1
    sender_task = asyncio.create_task(sender_loop(websocket, queue))
    sender_task.add_done_callback(
        lambda task: _supervise_sender(websocket, task),
    )
    state.lobby_revision += 1

    if replaced_connection is not None and replaced_connection is not websocket:
        asyncio.create_task(
            _close_connection(
                replaced_connection,
                4001,
                "Sessao retomada por uma nova conexao.",
            )
        )

    await enqueue_message(
        websocket,
        {
            "tipo": "bem_vindo",
            "player_id": player_id,
            "is_host": jogador.is_host,
            "fase": state.phase,
        },
    )
    if state.phase == "lobby":
        await broadcast_lobby()
    else:
        await _send_game(websocket)

    try:
        while True:
            try:
                data = json.loads(await websocket.receive_text())
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            if state.active_conn_by_player_id.get(player_id) is not websocket:
                break

            if data.get("tipo") in LOBBY_ACTIONS:
                response, broadcast_phase = await process_lobby_action(
                    data,
                    player_id,
                    _broadcast,
                )
            else:
                response, broadcast_phase = process_game_action(data, player_id)

            if response is not None:
                await enqueue_message(websocket, response)
            if broadcast_phase == "lobby":
                await broadcast_lobby()
            elif broadcast_phase == "game":
                await broadcast_game()

    except WebSocketDisconnect:
        pass

    finally:
        sender_task.cancel()
        await asyncio.gather(sender_task, return_exceptions=True)
        if websocket in state.connections:
            state.connections.remove(websocket)
        state.player_id_by_conn.pop(websocket, None)
        state.queues.pop(websocket, None)
        state.sent_world_revision.pop(websocket, None)

        is_current_connection = (
            state.active_conn_by_player_id.get(player_id) is websocket
        )
        if is_current_connection:
            state.active_conn_by_player_id.pop(player_id, None)
            jogador = state.players.get(player_id)
            if jogador is not None:
                jogador.controller = None

            if state.phase == "lobby":
                state.players.pop(player_id, None)
                session_token = state.player_session_by_id.pop(player_id, None)
                if (
                    session_token is not None
                    and state.player_id_by_session.get(session_token) == player_id
                ):
                    state.player_id_by_session.pop(session_token, None)
                if state.host_player_id == player_id:
                    state.host_player_id = None

            state.lobby_revision += 1
            if state.phase == "lobby":
                await broadcast_lobby()
