"""WebSocket connection manager for real-time review progress.

Maintains a registry of active WebSocket connections keyed by review_id
and broadcasts agent status updates to all connected clients for a review.
Optionally fans out messages through Redis Pub/Sub for multi-instance setups.
"""

import asyncio
import json
import logging
import uuid

from fastapi import WebSocket

from backend.config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Registry of active WebSocket connections grouped by review_id."""

    def __init__(self) -> None:
        # review_id (str) → list of active WebSocket connections
        self._connections: dict[str, list[WebSocket]] = {}
        self._redis_task: asyncio.Task | None = None
        self._instance_id = str(uuid.uuid4())

    async def startup(self) -> None:
        """Start optional Redis subscriber loop for multi-instance fan-out."""
        if not settings.redis_url:
            return

        if self._redis_task and not self._redis_task.done():
            return

        self._redis_task = asyncio.create_task(self._redis_subscriber_loop())
        logger.info("WS Redis pubsub enabled")

    async def shutdown(self) -> None:
        """Stop optional Redis subscriber task."""
        if self._redis_task is None:
            return
        self._redis_task.cancel()
        try:
            await self._redis_task
        except asyncio.CancelledError:
            pass
        self._redis_task = None

    async def _publish_redis(self, review_id: str, data: dict) -> None:
        """Publish websocket event to Redis channel.

        Uses lazy import so redis dependency stays optional.
        """
        if not settings.redis_url:
            return
        try:
            import redis.asyncio as redis  # noqa: PLC0415
        except Exception:
            logger.warning("Redis URL set but redis package missing; skipping pubsub")
            return

        payload = json.dumps(
            {
                "review_id": review_id,
                "data": data,
                "source_instance_id": self._instance_id,
            }
        )
        client = redis.from_url(settings.redis_url)
        try:
            await client.publish("ws:review-progress", payload)
        finally:
            await client.aclose()

    async def _redis_subscriber_loop(self) -> None:
        """Listen for Redis fan-out messages and rebroadcast locally."""
        if not settings.redis_url:
            return
        try:
            import redis.asyncio as redis  # noqa: PLC0415
        except Exception:
            logger.warning(
                "Redis URL set but redis package missing; skipping subscriber"
            )
            return

        client = redis.from_url(settings.redis_url)
        pubsub = client.pubsub()
        await pubsub.subscribe("ws:review-progress")

        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                raw = message.get("data")
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                if not isinstance(raw, str):
                    continue
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                source_instance_id = str(parsed.get("source_instance_id", ""))
                if source_instance_id == self._instance_id:
                    continue

                review_id = str(parsed.get("review_id", ""))
                data = parsed.get("data")
                if review_id and isinstance(data, dict):
                    await self._broadcast_local(review_id, data)
        except asyncio.CancelledError:
            raise
        finally:
            await pubsub.unsubscribe("ws:review-progress")
            await pubsub.aclose()
            await client.aclose()

    async def connect(self, review_id: str, websocket: WebSocket) -> None:
        """Accept a new connection and register it for the given review.

        Args:
            review_id: UUID string of the review being monitored.
            websocket: Incoming WebSocket connection (not yet accepted).
        """
        await websocket.accept()
        self._connections.setdefault(review_id, []).append(websocket)
        logger.info(
            "WS connect: review=%s total=%d",
            review_id,
            len(self._connections[review_id]),
        )

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
        await self._broadcast_local(str(review_id), data)
        await self._publish_redis(str(review_id), data)

    async def _broadcast_local(self, review_id: str, data: dict) -> None:
        """Broadcast to local process websocket clients only."""
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
