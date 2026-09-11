import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.playback_service import PlaybackSession, playback_cache

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/traffic")
async def traffic_replay(websocket: WebSocket) -> None:
    await websocket.accept()
    session = PlaybackSession(cache=playback_cache)
    logger.info("WebSocket client connected from %s", websocket.client)

    async def send(payload: dict) -> None:
        await websocket.send_json(payload)

    await session.attach(send)
    await send(
        {
            "type": "status",
            "state": session.state,
            "frame": session.frame,
            "speed": session.speed,
            "message": "Connected to trajectory replay. Send start to begin.",
            "cache_loaded": playback_cache.loaded,
            "min_frame": playback_cache.min_frame,
            "max_frame": playback_cache.max_frame,
        }
    )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await send({"type": "error", "detail": "WebSocket commands must be JSON objects."})
                continue
            if not isinstance(message, dict):
                await send({"type": "error", "detail": "WebSocket commands must be JSON objects."})
                continue
            response = await session.handle_command(message)
            await send(response)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception:
        logger.exception("WebSocket connection failed")
    finally:
        await session.close()
