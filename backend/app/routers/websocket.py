"""
WebSocket Router - Live Output Streaming
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db, async_session
from app.models.execution import Execution
from app.models.execution_log import ExecutionLog
from app.services.output_streamer import OutputStreamer
from app.auth.security import decode_token

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/execution/{execution_id}")
async def websocket_execution(
    websocket: WebSocket,
    execution_id: int,
):
    """
    WebSocket Endpoint für Live-Output einer Execution.

    Der Client sollte initial einen Token senden:
    {"type": "auth", "token": "jwt-token"}

    Danach werden alle Logs gestreamed:
    {"type": "stdout", "content": "...", "sequence_num": 1}
    {"type": "stderr", "content": "...", "sequence_num": 2}
    {"type": "finished", "status": "success", "exit_code": 0}
    """
    await OutputStreamer.connect(execution_id, websocket)

    try:
        # Warte auf Auth-Token
        auth_data = await websocket.receive_json()

        if auth_data.get("type") != "auth" or not auth_data.get("token"):
            await websocket.send_json({"type": "error", "message": "Auth erforderlich"})
            await websocket.close()
            return

        # Token validieren
        token_data = decode_token(auth_data["token"])
        if not token_data:
            await websocket.send_json({"type": "error", "message": "Ungültiger Token"})
            await websocket.close()
            return

        # Auth bestätigen
        await websocket.send_json({"type": "auth_ok", "user": token_data.username})

        # Bestehende Logs senden
        async with async_session() as db:
            result = await db.execute(
                select(ExecutionLog)
                .where(ExecutionLog.execution_id == execution_id)
                .order_by(ExecutionLog.sequence_num)
            )
            existing_logs = result.scalars().all()

            for log in existing_logs:
                await websocket.send_json({
                    "type": log.log_type,
                    "content": log.content,
                    "sequence_num": log.sequence_num,
                })

            # Execution-Status prüfen
            exec_result = await db.execute(
                select(Execution).where(Execution.id == execution_id)
            )
            execution = exec_result.scalar_one_or_none()

            if execution and execution.status in ["success", "failed", "cancelled"]:
                await websocket.send_json({
                    "type": "finished",
                    "status": execution.status,
                    "exit_code": execution.exit_code,
                    "duration": execution.duration_seconds,
                })

        # Auf neue Nachrichten warten (keep-alive)
        while True:
            try:
                data = await websocket.receive_json()
                # Ping/Pong für Keep-Alive
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        pass
    finally:
        OutputStreamer.disconnect(execution_id, websocket)
