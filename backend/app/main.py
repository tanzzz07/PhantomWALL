from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.db import AsyncSessionFactory, engine
from app.models import Base
from app.services.analytics import AnalyticsService
from app.services.websocket_manager import WebSocketManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.session_factory = AsyncSessionFactory

    # 1. Auto-migrate: add any missing columns to existing tables
    from app.services.auto_migrate import run_auto_migration
    await run_auto_migration(engine)

    # 2. Create any brand-new tables that don't exist yet
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    app.state.analytics_service = AnalyticsService(max_recent_events=settings.max_recent_events)
    app.state.websocket_manager = WebSocketManager()

    # Run database retention cleanup in background on startup
    import asyncio
    from app.services.retention import run_retention_cleanup
    asyncio.create_task(run_retention_cleanup(engine))

    yield
    await engine.dispose()


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Real-time tracker defense analytics for PhantomWall.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/dashboard-assets", StaticFiles(directory=static_dir), name="dashboard-assets")

app.include_router(api_router)


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {"message": "PhantomWall backend is running."}
