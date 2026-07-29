from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import json
import uuid

import core.player as player
from core.state import state
from connections.services.game_runtime import build_update, process_incoming


async def enqueue_message(conn: WebSocket, data: dict):
    q = state.queues.get(conn)
    if q is not None:
        await q.put(data)


async def sender_loop(conn: WebSocket, q: asyncio.Queue):
    while True:
        data = await q.get()
        await conn.send_json(data)


async def websocket_handler(websocket: WebSocket):
    await websocket.accept()
    state.connections.append(websocket)

    player_id = str(uuid.uuid4())
    state.player_id_by_conn[websocket] = player_id

    state.players[player_id] = player.Player(player_id, websocket)

    q = asyncio.Queue()
    state.queues[websocket] = q
    sender_task = asyncio.create_task(sender_loop(websocket, q))

    await enqueue_message(websocket, {"tipo": "bem_vindo", "player_id": player_id})
    await enqueue_message(websocket, build_update(player_id))

    try:
        while True:
            try:
                data = json.loads(await websocket.receive_text())
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            response = process_incoming(data, player_id)
            await enqueue_message(websocket, response)

    except WebSocketDisconnect:
        pass

    finally:
        sender_task.cancel()
        state.players.pop(player_id, None)
        await asyncio.gather(sender_task, return_exceptions=True)
        if websocket in state.connections:
            state.connections.remove(websocket)
        state.player_id_by_conn.pop(websocket, None)
        state.queues.pop(websocket, None)
