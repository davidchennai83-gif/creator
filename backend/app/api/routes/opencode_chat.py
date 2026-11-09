"""In-app OpenCode chat: models, sessions, and a streaming prompt proxy."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.schemas.common import success
from app.services import opencode_bridge as bridge

router = APIRouter()


class ModelRef(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    providerID: str = Field(min_length=1, max_length=100)
    variant: str | None = Field(default=None, max_length=60)


class NewSession(BaseModel):
    model: ModelRef | None = None
    title: str | None = Field(default=None, max_length=120)


class ChatIn(BaseModel):
    sessionId: str = Field(min_length=3, max_length=120)
    text: str = Field(min_length=1, max_length=32000)


class ModelChange(BaseModel):
    model: ModelRef


async def attempt(call):
    try:
        return success(await call)
    except bridge.BridgeError as exc:
        raise HTTPException(503, str(exc))


@router.get("/status")
async def status():
    try:
        info = await bridge.probe()
    except bridge.BridgeError as exc:
        return success({"running": True, "reachable": False, "message": str(exc),
                        "fallback": bridge.fallback_state()})
    return success({"running": True, "reachable": info is not None, "info": info,
                    "fallback": bridge.fallback_state()})


@router.get("/models")
async def models():
    return await attempt(bridge.list_models())


@router.post("/sessions")
async def create_session(data: NewSession):
    model = bridge.model_ref(data.model.model_dump()) if data.model else None
    return await attempt(bridge.create_session(model, data.title))


@router.get("/sessions/{session_id}/messages")
async def messages(session_id: str):
    return await attempt(bridge.get_messages(session_id))


@router.post("/sessions/{session_id}/model")
async def change_model(session_id: str, data: ModelChange):
    return await attempt(bridge.set_model(session_id, bridge.model_ref(data.model.model_dump())))


@router.post("/sessions/{session_id}/interrupt")
async def stop(session_id: str):
    return await attempt(bridge.interrupt(session_id))


@router.post("/chat")
async def chat(data: ChatIn):
    """Stream one assistant reply as Server-Sent Events.

    Frames: accepted | started | step | tool | tool-done | delta | text |
    error | interrupted | done. The browser reads this with fetch() so the
    normal Authorization header keeps working.
    """
    return StreamingResponse(
        bridge.stream_chat(data.sessionId, data.text),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
