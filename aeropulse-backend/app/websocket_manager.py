import json
import logging
from fastapi import WebSocket

logger = logging.getLogger("aeropulse.ws")


class ConnectionManager:
    """Holds active admin-dashboard WebSocket connections and fans out
    every event received from Redis to all of them. One dashboard
    instance == one connection; the browser never polls once connected."""

    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()
