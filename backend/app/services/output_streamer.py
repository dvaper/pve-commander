"""
Output Streamer - WebSocket Broadcast für Live-Output
"""
import json
from typing import Dict, Set
from fastapi import WebSocket


class OutputStreamer:
    """Verwaltet WebSocket-Verbindungen für Live-Output"""

    # Aktive Verbindungen pro Execution-ID
    _connections: Dict[int, Set[WebSocket]] = {}

    @classmethod
    async def connect(cls, execution_id: int, websocket: WebSocket):
        """Registriert eine neue WebSocket-Verbindung"""
        await websocket.accept()

        if execution_id not in cls._connections:
            cls._connections[execution_id] = set()

        cls._connections[execution_id].add(websocket)

    @classmethod
    def disconnect(cls, execution_id: int, websocket: WebSocket):
        """Entfernt eine WebSocket-Verbindung"""
        if execution_id in cls._connections:
            cls._connections[execution_id].discard(websocket)

            # Leere Sets aufräumen
            if not cls._connections[execution_id]:
                del cls._connections[execution_id]

    @classmethod
    async def broadcast(cls, execution_id: int, message: dict):
        """Sendet eine Nachricht an alle Verbindungen einer Execution"""
        if execution_id not in cls._connections:
            return

        # Kopie der Verbindungen erstellen (für sichere Iteration)
        connections = cls._connections[execution_id].copy()

        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception:
                # Verbindung ist fehlerhaft - entfernen
                cls.disconnect(execution_id, websocket)

    @classmethod
    async def send_to_one(cls, websocket: WebSocket, message: dict):
        """Sendet eine Nachricht an eine einzelne Verbindung"""
        try:
            await websocket.send_json(message)
        except Exception:
            pass

    @classmethod
    def get_connection_count(cls, execution_id: int) -> int:
        """Gibt die Anzahl aktiver Verbindungen zurück"""
        if execution_id not in cls._connections:
            return 0
        return len(cls._connections[execution_id])
