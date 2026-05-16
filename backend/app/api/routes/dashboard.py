from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["dashboard"])

STATIC_DIR = Path(__file__).resolve().parents[2] / "static"


@router.get("/dashboard", include_in_schema=False)
async def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "dashboard.html")

