"""
WebSocket API for real-time sync events

Provides real-time communication for:
- Sync progress updates
- Sync completion notifications
- Error notifications

BLOCK_SYNC 통신 인터페이스 - BLOCK_FRONTEND에서 WebSocket으로 구독
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from datetime import datetime
from typing import List, Dict, Any
import json
import asyncio

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """WebSocket connection manager for broadcast messaging."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WS] Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"[WS] Client disconnected. Total: {len(self.active_connections)}")

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Send a message to a specific client."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"[WS] Error sending message: {e}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WS] Error broadcasting: {e}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws/sync")
async def websocket_sync_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for sync events.

    Message Types (Server → Client):
    - sync_start: Sync operation started
    - sync_progress: Sync progress update
    - sync_complete: Sync operation completed
    - sync_error: Sync operation failed
    - file_found: New file discovered
    - sheet_updated: Google Sheet row updated

    Message Types (Client → Server):
    - ping: Keep-alive message (server responds with pong)
    """
    await manager.connect(websocket)

    # Send welcome message
    await manager.send_personal_message(
        {
            "type": "connected",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {"message": "Connected to sync WebSocket"},
        },
        websocket,
    )

    try:
        while True:
            # Receive messages from client (keep-alive or commands)
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                msg_type = message.get("type", "")

                if msg_type == "ping":
                    # Respond to ping with pong
                    await manager.send_personal_message(
                        {
                            "type": "pong",
                            "timestamp": datetime.utcnow().isoformat(),
                            "payload": {},
                        },
                        websocket,
                    )
            except json.JSONDecodeError:
                # Invalid JSON, ignore
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Helper functions for broadcasting sync events (called from sync service)


async def broadcast_sync_start(sync_id: str, source: str, triggered_by: str = "manual"):
    """Broadcast sync start event."""
    await manager.broadcast(
        {
            "type": "sync_start",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "sync_id": sync_id,
                "source": source,
                "triggered_by": triggered_by,
            },
        }
    )


async def broadcast_sync_progress(
    sync_id: str,
    source: str,
    current: int,
    total: int,
    current_file: str = None,
):
    """Broadcast sync progress update."""
    percentage = (current / total * 100) if total > 0 else 0
    await manager.broadcast(
        {
            "type": "sync_progress",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "sync_id": sync_id,
                "source": source,
                "current": current,
                "total": total,
                "current_file": current_file,
                "percentage": round(percentage, 1),
            },
        }
    )


async def broadcast_sync_complete(
    sync_id: str,
    source: str,
    duration_ms: int,
    files_processed: int,
    files_added: int,
    files_updated: int,
    errors: int,
):
    """Broadcast sync completion event."""
    await manager.broadcast(
        {
            "type": "sync_complete",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "sync_id": sync_id,
                "source": source,
                "duration_ms": duration_ms,
                "files_processed": files_processed,
                "files_added": files_added,
                "files_updated": files_updated,
                "errors": errors,
            },
        }
    )


async def broadcast_sync_error(sync_id: str, source: str, error_code: str, message: str):
    """Broadcast sync error event."""
    await manager.broadcast(
        {
            "type": "sync_error",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "sync_id": sync_id,
                "source": source,
                "error_code": error_code,
                "message": message,
            },
        }
    )


def get_connection_count() -> int:
    """Get current number of active WebSocket connections."""
    return len(manager.active_connections)
