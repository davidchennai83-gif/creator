"""Socket.IO server for the local Windows recorder agent.

The wire protocol is kept identical to the original RCM Automation Hub agent so
`recorder_agent.py` stays drop-in compatible:

  agent -> server   recorder_register   {version, platform, hostname, token}
  agent -> server   recorder_event      {type, msg, ...}      (relayed to browsers)
  agent -> server   recorder_save       {name, record_type, script}
  server -> agent   recorder_command    {cmd: start|stop|run|stop_run|debug_input|ping}

Live Monitor is intentionally absent — only the Recorder feature is ported.

Every connection is authenticated at handshake time: agents present the shared
RECORDER_AGENT_TOKEN and browsers present their live access token. Unauthenticated
sockets can neither listen to recorder events nor write scripts to disk.
"""
import logging
from uuid import UUID

import socketio

from app.config.settings import settings
from app.core.security import decode_access_token
from app.database.engine import async_session_maker
from app.models.user import Session, User
from app.recorder import agents, store
from app.utils.time import utcnow

log = logging.getLogger(__name__)

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")


def _agent_token() -> str:
    return settings.RECORDER_AGENT_TOKEN.get_secret_value().strip()


async def _browser_identity(auth: dict) -> dict | None:
    """Return the live browser identity, including its role, when authorized."""
    payload = decode_access_token(str((auth or {}).get("token") or ""))
    try:
        user_id, session_id = UUID(payload["sub"]), UUID(payload["sid"])
    except (TypeError, KeyError, ValueError):
        return None
    async with async_session_maker() as db:
        session = await db.get(Session, session_id)
        user = await db.get(User, user_id)
        if not (user and user.is_active and session and session.user_id == user_id
                and not session.revoked_at and session.expires_at > utcnow()):
            return None
        return {"agent": False, "user_id": str(user_id), "role": user.role.value}


async def _identity(sid) -> dict:
    try:
        return await sio.get_session(sid) or {}
    except KeyError:
        return {}


async def _is_agent(sid) -> bool:
    return bool((await _identity(sid)).get("agent"))


async def _can_write(sid) -> bool:
    identity = await _identity(sid)
    return bool(identity.get("agent") or identity.get("role") in ("SUPER_ADMIN", "ADMIN", "EDITOR"))


@sio.event
async def connect(sid, environ, auth):
    auth = auth or {}
    presented = str(auth.get("token") or "").strip()
    expected = _agent_token()
    if expected:
        # Shared secret configured: only the agent may use it, browsers fall through
        # to the session check below.
        if presented == expected:
            await sio.save_session(sid, {"agent": True, "role": "AGENT"})
            return True
    elif not presented and not environ.get("HTTP_ORIGIN"):
        # No secret configured (LAN/dev default): non-browser clients are the local
        # agent. Browser pages always carry an Origin header, so they must still
        # authenticate with a live access token.
        await sio.save_session(sid, {"agent": True, "role": "AGENT"})
        return True
    identity = await _browser_identity(auth)
    if identity:
        await sio.save_session(sid, identity)
        return True
    log.warning("recorder socket rejected: missing or invalid credentials")
    await sio.disconnect(sid)
    return False


@sio.event
async def recorder_register(sid, data):
    if not await _is_agent(sid):
        log.warning("recorder_register rejected for non-agent socket %s", sid)
        await sio.emit("recorder_event", {"type": "error", "msg": "Only the local recorder agent can register"})
        return
    data = data or {}
    record = agents.register(sid, data)
    await sio.emit("recorder_agent_status", {"agents": agents.all_agents()})
    log.info("recorder agent connected: %s (%s)", record["hostname"], sid)


@sio.event
async def recorder_event(sid, data):
    """Relay an agent event to every connected browser."""
    if not await _is_agent(sid):
        return
    await sio.emit("recorder_event", data or {})


@sio.event
async def recorder_save(sid, data):
    """Persist a recorded script and tell the browsers it landed."""
    if not await _can_write(sid):
        log.warning("recorder_save rejected for read-only socket %s", sid)
        await sio.emit("recorder_event", {"type": "error", "msg": "You do not have permission to save recordings"})
        return
    data = data or {}
    name = data.get("name") or "recording"
    record_type = store.safe_type(data.get("record_type", "desktop"))
    script = data.get("script", "")
    try:
        filename = store.write(name, record_type, script)
    except (OSError, ValueError) as exc:
        log.warning("recorder save failed: %s", exc)
        await sio.emit("recorder_event", {"type": "error", "msg": f"Save failed: {exc}"})
        return
    log.info("recorder script saved: %s/%s", record_type, filename)
    await sio.emit(
        "recorder_event",
        {
            "type": "saved",
            "name": filename,
            "record_type": record_type,
            "msg": f"Script saved: {filename}",
            "event_count": data.get("event_count", 0),
        },
    )


@sio.event
async def disconnect(sid):
    if agents.unregister(sid):
        await sio.emit("recorder_agent_status", {"agents": agents.all_agents()})


def asgi_app(fastapi_app):
    """Wrap the FastAPI application so /socket.io is handled by Socket.IO."""
    return socketio.ASGIApp(sio, fastapi_app, socketio_path="socket.io")
