from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..websocket_manager import manager

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/live")
async def live_feed(websocket: WebSocket):
    """
    The admin dashboard opens exactly one of these. Every event published
    to Redis (flight status changes, incidents raised/resolved/breached,
    tickets verified, coupons issued) gets forwarded here in real time —
    see main.py's startup task for the Redis -> WebSocket bridge.
    """
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect inbound messages, but keep the socket alive
            # and detect client disconnects promptly.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
