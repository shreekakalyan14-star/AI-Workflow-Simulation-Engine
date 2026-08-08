"""
In-memory WebSocket connection manager, keyed by company_id.

FEATURE 17: real-time updates for manager chat, team chat, notifications,
and live task updates. This is a single-process implementation — see
docs/VERIFICATION.md / docs/ARCHITECTURE.md for the note on what a
multi-instance deployment would need instead (Redis pub/sub).
"""
import json
from typing import Dict, List

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, company_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(company_id, []).append(websocket)

    def disconnect(self, company_id: str, websocket: WebSocket) -> None:
        conns = self._connections.get(company_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns and company_id in self._connections:
            del self._connections[company_id]

    async def broadcast(self, company_id: str, event_type: str, data: dict) -> None:
        conns = self._connections.get(company_id, [])
        if not conns:
            return
        payload = json.dumps({"type": event_type, "data": data}, default=str)
        dead = []
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(company_id, ws)


manager = ConnectionManager()
