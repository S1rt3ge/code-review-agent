"""FastAPI application entry point.

Configures CORS, includes all API routers, provides a health-check
endpoint, a WebSocket endpoint for real-time agent progress, and
startup/shutdown lifecycle hooks for the database engine.

Functions:
    health_check: GET /health -- application health probe.
    websocket_progress: WS /ws/progress/{review_id} -- real-time agent updates.
    startup: Verify database connectivity on startup.
    shutdown: Dispose of the async engine on shutdown.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from backend.config import settings
from backend.models.schemas import HealthResponse
from backend.routers import auth, dashboard, github, repositories, reviews
from backend.routers import settings as settings_router
from backend.services.ws_manager import ws_manager
from backend.utils.database import async_session_factory, engine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler: startup and shutdown logic.

    On startup, verifies that the database is reachable.
    On shutdown, disposes of the SQLAlchemy async engine.
    """
    # Startup
    logger.info(f"Starting application (env={settings.app_env})")
    try:
        async with asyncio.timeout(10):
            async with async_session_factory() as session:
                await session.execute(text("SELECT 1"))
        logger.info("Database connection verified")
    except Exception as e:
        logger.warning(f"Database not reachable at startup: {e}")

    yield

    # Shutdown
    logger.info("Shutting down application")
    await engine.dispose()
    logger.info("Database engine disposed")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Code Review Agent",
    description="Multi-agent code review system powered by LangGraph",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers (all under /api prefix)
app.include_router(auth.router, prefix="/api")
app.include_router(github.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(repositories.router, prefix="/api")

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """Return application health status.

    Attempts a lightweight database query.  Reports ``connected`` when
    the query succeeds and ``disconnected`` otherwise.

    Returns:
        HealthResponse with status, environment, and database state.
    """
    db_status = "disconnected"
    try:
        async with asyncio.timeout(5):
            async with async_session_factory() as session:
                await session.execute(text("SELECT 1"))
                db_status = "connected"
    except Exception as e:
        logger.warning(f"Health check DB probe failed: {e}")

    return HealthResponse(
        status="ok",
        environment=settings.app_env,
        database=db_status,
    )


# ---------------------------------------------------------------------------
# WebSocket — real-time agent progress
# ---------------------------------------------------------------------------


@app.websocket("/ws/progress/{review_id}")
async def websocket_progress(websocket: WebSocket, review_id: str) -> None:
    """WebSocket endpoint for real-time review progress updates.

    Clients connect while a review is being analyzed to receive
    incremental status messages from each agent as they start and finish.
    The connection stays open until the client disconnects; no messages
    need to be sent from the client side.

    Message format pushed to clients:
        {"agent_name": "security", "status": "running"|"done"|"error"}

    Args:
        websocket: The WebSocket connection.
        review_id: UUID of the review being monitored.
    """
    await ws_manager.connect(review_id, websocket)
    try:
        # Keep the connection alive; updates are pushed by the analyzer.
        while True:
            # receive_text() blocks until the client sends or disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(review_id, websocket)


# ---------------------------------------------------------------------------
# Serve built React frontend (must be last — catch-all matches everything)
# ---------------------------------------------------------------------------

_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        """Serve index.html for all non-API routes (React Router SPA)."""
        return FileResponse(_FRONTEND_DIST / "index.html")
