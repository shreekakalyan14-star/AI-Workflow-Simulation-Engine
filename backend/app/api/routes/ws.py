"""
FEATURE 17: WebSocket endpoint for real-time chat + notifications + task
updates. Auth is via a `token` query parameter (browsers can't set custom
headers on the WS handshake), validated the same way as REST bearer
tokens, then scoped so a student can only subscribe to their own company.
"""
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import decode_token
from app.models.company import Company
from app.websockets.manager import manager as ws_manager

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/companies/{company_id}")
async def company_ws(websocket: WebSocket, company_id: uuid.UUID, token: str = Query(...)):
    try:
        claims = decode_token(token)
    except Exception:
        await websocket.close(code=4401)
        return

    student_id = claims.get("sub") or claims.get("student_id")
    db: Session = SessionLocal()
    try:
        company = db.get(Company, company_id)
        if company is None or company.student_id != student_id:
            await websocket.close(code=4403)
            return
    finally:
        db.close()

    key = str(company_id)
    await ws_manager.connect(key, websocket)
    try:
        while True:
            # We don't expect inbound messages on this channel (it's a
            # push feed) — just keep the connection alive and drop
            # anything the client sends.
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(key, websocket)
