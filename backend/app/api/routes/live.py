from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.services.auth import decode_admin_access_token

router = APIRouter(tags=["live"])


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401, reason="Missing token.")
        return

    try:
        payload = decode_admin_access_token(token, get_settings())
        if payload.get("scope") not in ("admin", "user"):
            raise ValueError("Invalid scope")
    except Exception:
        await websocket.close(code=4401, reason="Invalid token.")
        return

    analytics_service = websocket.app.state.analytics_service
    websocket_manager = websocket.app.state.websocket_manager
    await websocket_manager.connect(websocket)

    try:
        async_session_factory = websocket.app.state.session_factory
        async with async_session_factory() as session:
            user_id = payload.get("user_id") if payload.get("scope") == "user" else None
            snapshot = await analytics_service.get_stats(
                session=session,
                user_id=user_id,
                recent_limit=25,
            )
        await websocket.send_json(
            {"type": "stats.snapshot", "data": snapshot.model_dump(mode="json")}
        )

        while True:
            message = await websocket.receive_text()
            if message.lower() == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket)
    except Exception:
        await websocket_manager.disconnect(websocket)

