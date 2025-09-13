from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_sessions: Dict[str, Dict] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_sessions[session_id] = {
            "websocket": websocket,
            "vapi_call_active": False,
            "listening": True
        }
        logger.info(f"Client {session_id} connected")

    def disconnect(self, websocket: WebSocket, session_id: str):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if session_id in self.user_sessions:
            del self.user_sessions[session_id]
        logger.info(f"Client {session_id} disconnected")

    async def send_personal_message(self, message: str, session_id: str):
        if session_id in self.user_sessions:
            websocket = self.user_sessions[session_id]["websocket"]
            await websocket.send_text(message)

    async def send_json_message(self, data: dict, session_id: str):
        if session_id in self.user_sessions:
            websocket = self.user_sessions[session_id]["websocket"]
            await websocket.send_json(data)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

    def is_vapi_active(self, session_id: str) -> bool:
        return self.user_sessions.get(session_id, {}).get("vapi_call_active", False)

    def set_vapi_status(self, session_id: str, active: bool):
        if session_id in self.user_sessions:
            self.user_sessions[session_id]["vapi_call_active"] = active

    def set_listening_status(self, session_id: str, listening: bool):
        if session_id in self.user_sessions:
            self.user_sessions[session_id]["listening"] = listening

manager = ConnectionManager()