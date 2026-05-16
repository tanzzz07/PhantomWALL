from fastapi import APIRouter

from app.api.routes.analytics import router as analytics_router
from app.api.routes.auth import router as auth_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.health import router as health_router
from app.api.routes.installs import router as installs_router
from app.api.routes.live import router as live_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(installs_router)
api_router.include_router(analytics_router)
api_router.include_router(live_router)
api_router.include_router(dashboard_router)
