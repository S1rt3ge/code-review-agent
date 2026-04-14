"""WebSocket connection manager for real-time review progress.

Maintains a registry of active WebSocket connections keyed by review_id
and broadcasts agent status updates to all connected clients for a review.

Classes:
    ConnectionManager: Manages connect/disconnect/broadcast lifecycle.

Module-level instance:
    ws_manager: Singleton used across the application.
"""

import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Registry of active WebSocket connections grouped by review_id."""

    def __init__(self) -> None:
        # review_id (str) → list of active WebSocket connections
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, review_id: str, websocket: WebSocket) -> None:
        """Accept a new connection and register it for the given review.

        Args:
            review_id: UUID string of the review being monitored.
            websocket: Incoming WebSocket connection (not yet accepted).
        """
        await websocket.accept()
        self._connections.setdefault(review_id, []).append(websocket)
        logger.info("WS connect: review=%s total=%d", review_id, len(self._connections[review_id]))

    def disconnect(self, review_id: str, websocket: WebSocket) -> None:
        """Remove a connection from the registry.

        Args:
            review_id: UUID string of the review.
            websocket: The connection to remove.
        """
        conns = self._connections.get(review_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self._connections.pop(review_id, None)
        logger.info("WS disconnect: review=%s remaining=%d", review_id, len(conns))

    async def broadcast(self, review_id: str, data: dict) -> None:
        """Send a JSON message to all clients watching this review.

        Dead connections are silently removed from the registry.

        Args:
            review_id: UUID string of the review.
            data: JSON-serialisable dict to send.
        """
        conns = list(self._connections.get(str(review_id), []))
        if not conns:
            return

        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(str(review_id), ws)


# Singleton — imported by main.py (WS endpoint) and analyzer.py (broadcaster).
ws_manager = ConnectionManager()
