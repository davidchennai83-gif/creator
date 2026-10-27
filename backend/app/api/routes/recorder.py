"""Recorder REST API.

Mirrors the original RCM Automation Hub /api/recorder/* surface, minus
Live Monitor. The two debugger endpoints that the original wired to
/api/live-monitor/debug-input* are re-homed here as /recorder/debug-input,
because the underlying relay is agent-side, not server-side.

The local agent itself connects over Socket.IO, not REST; these routes only
inspect connected agents and relay commands to them.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.deps import editor
from app.config.settings import BACKEND_DIR
from app.recorder import agents, store
from app.recorder.socket_server import sio
from app.schemas.common import success

router = APIRouter()

AGENT_FILES = {"recorder_agent.py", "Start_Recorder_Agent.bat"}
_TYPED = {"web", "desktop"}


class Command(BaseModel):
    cmd: str
    sid: str | None = None
    type: str = "desktop"
    url: str = ""
    app_path: str = ""
    name: str = ""


class RunScript(BaseModel):
    name: str = ""
    type: str = "web"
    content: str | None = None
    debug: bool = False
    sid: str | None = None


class SaveContent(BaseModel):
    name: str
    type: str = "web"
    content: str = ""


class DeleteRecording(BaseModel):
    name: str
    type: str = "web"


class DebugInput(BaseModel):
    input: str = "n"
    sid: str | None = None


def _require_agent(sid: str | None) -> str:
    resolved = agents.resolve_sid(sid)
    if not resolved:
        # Never silently fall back to a different machine when a specific agent was named.
        raise HTTPException(409, "That recorder agent is no longer connected. Refresh the agent list and try again."
                            if sid else
                            "No recorder agent connected. Start recorder_agent.py on the machine you want to drive.")
    return resolved


async def _emit(payload: dict, sid: str | None) -> str:
    target = _require_agent(sid)
    await sio.emit("recorder_command", payload, to=target)
    return target


@router.get("/agents")
async def list_agents(user=Depends(editor)):
    return success({"agents": agents.all_agents(), "count": agents.count()})


@router.post("/command")
async def command(data: Command, user=Depends(editor)):
    payload = {
        "cmd": data.cmd,
        "type": data.type if data.type in _TYPED else "desktop",
        "url": data.url,
        "app_path": data.app_path,
        "name": data.name,
    }
    target = await _emit(payload, data.sid)
    return success({"ok": True, "sid": target})


@router.get("/list")
async def list_recordings(user=Depends(editor)):
    return success({"recordings": store.listing()})


@router.get("/content/{name}")
async def read_recording(name: str, user=Depends(editor)):
    found = store.read(name)
    if not found:
        raise HTTPException(404, "File not found")
    return success(found)


@router.post("/save-content")
async def save_recording(data: SaveContent, user=Depends(editor)):
    if not data.name.strip():
        raise HTTPException(400, "File name is required")
    try:
        name = store.write(data.name, data.type, data.content)
    except (OSError, ValueError) as exc:
        raise HTTPException(400, str(exc))
    return success({"name": name, "type": store.safe_type(data.type)})


@router.post("/run")
async def run_recording(data: RunScript, user=Depends(editor)):
    script = data.content
    if script is None:
        found = store.read(data.name)
        if not found:
            raise HTTPException(404, "File not found")
        script = found["content"]
    target = await _emit(
        {
            "cmd": "run",
            "name": data.name or "script",
            "record_type": data.type if data.type in _TYPED else "web",
            "script": script,
            "debug": data.debug,
        },
        data.sid,
    )
    return success({"ok": True, "sid": target, "debug": data.debug})


@router.post("/stop-run")
async def stop_run(data: DebugInput, user=Depends(editor)):
    target = await _emit({"cmd": "stop_run"}, data.sid)
    return success({"ok": True, "sid": target})


@router.post("/debug-input")
async def debug_input(data: DebugInput, user=Depends(editor)):
    """Forward a pdb command ('n' step, 'c' continue) to the paused agent run."""
    command_text = (data.input or "n").strip() or "n"
    target = await _emit({"cmd": "debug_input", "input": command_text}, data.sid)
    return success({"ok": True, "sid": target, "input": command_text})


@router.post("/delete")
async def delete_recording(data: DeleteRecording, user=Depends(editor)):
    if not store.delete(data.name):
        raise HTTPException(404, "File not found")
    return success({"name": store.safe_name(data.name)})


@router.get("/download/{name}")
async def download_recording(name: str, user=Depends(editor)):
    found = store.find(name)
    if not found:
        raise HTTPException(404, "File not found")
    path, _ = found
    return FileResponse(path, media_type="text/x-python", filename=path.name)


@router.get("/download-agent/{filename}")
async def download_agent_file(filename: str, user=Depends(editor)):
    if filename not in AGENT_FILES:
        raise HTTPException(403, "Not allowed")
    for base in (BACKEND_DIR / "recorder" / "agent", BACKEND_DIR):
        candidate = base / filename
        if candidate.is_file():
            return FileResponse(candidate, media_type="application/octet-stream", filename=filename)
    raise HTTPException(404, "File not found")
