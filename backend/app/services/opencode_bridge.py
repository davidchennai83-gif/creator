"""Bridge to the local OpenCode v2 HTTP API.

The web UI talks to the backend (bearer auth); the backend talks to the
OpenCode server over loopback with HTTP Basic auth. When nothing is listening
we start the Desktop CLI ourselves -- it carries the signed-in credentials,
while the npm build ships with expired keys.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import urlparse

import httpx

from app.config.settings import BACKEND_DIR, PROJECT_DIR, settings
from app.services import agent_fallback

log = logging.getLogger(__name__)

AUTH_USER = "opencode"
# A single prompt may legitimately take minutes (tool calls, builds). The idle
# timeout is what ends a stream when the agent goes silent.
STREAM_IDLE_TIMEOUT = 300
STREAM_MAX_SECONDS = 1800
# Comment frames keep mobile/proxy connections open while the agent is quiet.
HEARTBEAT_SECONDS = 15


class BridgeError(RuntimeError):
    """Raised when the OpenCode server cannot be reached or started."""


_lock = asyncio.Lock()
_process: subprocess.Popen | None = None
_log_handle: Any = None
_client: httpx.AsyncClient | None = None


def base_url() -> str:
    return settings.OPENCODE_URL.rstrip("/")


def workdir() -> Path:
    configured = settings.OPENCODE_WORKDIR.strip()
    return Path(configured).expanduser() if configured else PROJECT_DIR


def client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=base_url(),
            auth=httpx.BasicAuth(AUTH_USER, settings.OPENCODE_SERVER_PASSWORD.get_secret_value()),
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
    return _client


def find_cli() -> Path | None:
    """Locate opencode-cli.exe: explicit setting first, then newest Desktop CLI."""
    configured = settings.OPENCODE_CLI_PATH.strip()
    if configured:
        found = Path(configured).expanduser()
        return found if found.is_file() else None
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", "")) / "ai.opencode.desktop" / "cli"
        if root.is_dir():
            candidates = [p for p in root.glob("*/opencode-cli.exe") if p.is_file()]
            if candidates:
                return max(candidates, key=lambda p: [int(n) for n in re.findall(r"\d+", p.parent.name)] or [0])
    return None


async def probe() -> dict | None:
    """Return /api/info when the server answers with our password."""
    try:
        response = await client().get("/api/info", timeout=5.0)
    except httpx.HTTPError:
        return None
    if response.status_code == 401:
        raise BridgeError(
            f"An OpenCode server is already listening on {base_url()} with a different "
            "password. Stop it, or set OPENCODE_SERVER_PASSWORD to match it."
        )
    if response.status_code >= 400:
        return None
    try:
        return response.json()
    except ValueError:
        return None


def _start_process() -> None:
    global _process, _log_handle
    if _process is not None and _process.poll() is None:
        return
    cli = find_cli()
    if cli is None:
        raise BridgeError(
            "OpenCode CLI was not found. Install OpenCode Desktop, or set "
            "OPENCODE_CLI_PATH to opencode-cli.exe."
        )
    url = urlparse(base_url())
    host = url.hostname or "127.0.0.1"
    port = url.port or 4096

    log_dir = BACKEND_DIR / "storage" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    _log_handle = open(log_dir / "opencode-server.log", "a", encoding="utf-8", buffering=1)

    env = os.environ.copy()
    env["OPENCODE_SERVER_PASSWORD"] = settings.OPENCODE_SERVER_PASSWORD.get_secret_value()
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    _process = subprocess.Popen(  # noqa: S603 - fixed local binary
        [str(cli), "serve", "--port", str(port), "--hostname", host],
        cwd=str(workdir()),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=_log_handle,
        stderr=subprocess.STDOUT,
        creationflags=flags,
    )
    log.info("Started OpenCode server (pid %s) on %s", _process.pid, base_url())


async def ensure_server() -> dict:
    """Return server info, launching the CLI if it is not already running."""
    async with _lock:
        info = await probe()
        if info is not None:
            return info
        if not settings.OPENCODE_AUTOSTART:
            raise BridgeError(
                f"OpenCode is not running on {base_url()}. Start `opencode-cli serve` "
                "or enable OPENCODE_AUTOSTART."
            )
        _start_process()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + settings.OPENCODE_START_TIMEOUT
        while loop.time() < deadline:
            await asyncio.sleep(0.4)
            info = await probe()
            if info is not None:
                return info
            if _process is not None and _process.poll() is not None:
                raise BridgeError(
                    "OpenCode exited while starting. See "
                    f"{BACKEND_DIR / 'storage' / 'logs' / 'opencode-server.log'}."
                )
        raise BridgeError("OpenCode did not become ready in time. Check the server log.")


async def _json(method: str, path: str, **kwargs) -> Any:
    await ensure_server()
    try:
        response = await client().request(method, path, **kwargs)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:400]
        raise BridgeError(f"OpenCode returned {exc.response.status_code}: {detail}") from exc
    except httpx.HTTPError as exc:
        raise BridgeError(f"OpenCode request failed: {exc}") from exc
    if not response.content:
        return None
    return response.json()


def _default_model_ref(models: list[dict]) -> dict | None:
    preferred = settings.OPENCODE_DEFAULT_MODEL.strip()
    if "/" in preferred:
        provider, model_id = preferred.split("/", 1)
        for model in models:
            if model.get("providerID") == provider and model.get("id") == model_id:
                return {"id": model_id, "providerID": provider}
    # Prefer a free model so a first message never needs paid credits.
    for model in models:
        if model.get("free"):
            return {"id": model["id"], "providerID": model["providerID"]}
    return {"id": models[0]["id"], "providerID": models[0]["providerID"]} if models else None


async def list_models() -> dict:
    payload = await _json("GET", "/api/model")
    rows = payload.get("data", []) if isinstance(payload, dict) else payload or []
    models = []
    for row in rows:
        if row.get("type") not in (None, "chat"):
            continue
        if row.get("enabled") is False:
            continue
        capabilities = row.get("capabilities") or {}
        # The OpenCode agent always runs with tools. A model that explicitly
        # declares tools:false (e.g. Ollama's deepseek-coder-v2) fails every
        # prompt with "does not support tools", so keep it out of the picker.
        if capabilities.get("tools") is False:
            continue
        cost = (row.get("cost") or [{}])[0] or {}
        models.append({
            "id": row.get("modelID") or row.get("id"),
            "providerID": row.get("providerID"),
            "name": row.get("name") or row.get("id"),
            "free": float(cost.get("input") or 0) == 0 and float(cost.get("output") or 0) == 0,
            "status": row.get("status", "active"),
            "context": (row.get("limit") or {}).get("context"),
            "tools": capabilities.get("tools") is not False,
        })
    models.sort(key=lambda m: (m["providerID"] or "", m["name"] or ""))
    return {
        "models": models,
        "default": _default_model_ref(models),
        "providers": sorted({m["providerID"] for m in models if m["providerID"]}),
    }


def model_ref(model: dict | None) -> dict | None:
    if not model:
        return None
    provider = model.get("providerID") or model.get("provider")
    model_id = model.get("id") or model.get("modelID")
    if not provider or not model_id:
        return None
    ref = {"id": model_id, "providerID": provider}
    if model.get("variant"):
        ref["variant"] = model["variant"]
    return ref


async def create_session(model: dict | None = None, title: str | None = None) -> dict:
    if model is None:
        listing = await list_models()
        model = listing["default"]
    body: dict[str, Any] = {
        "title": (title or "Web chat")[:120],
        "location": {"directory": str(workdir())},
    }
    if model:
        body["model"] = model
    payload = await _json("POST", "/api/session", json=body)
    return payload.get("data", payload)


async def set_model(session_id: str, model: dict) -> None:
    await _json("POST", f"/api/session/{session_id}/model", json={"model": model})


async def get_messages(session_id: str) -> list[dict]:
    payload = await _json("GET", f"/api/session/{session_id}/message")
    rows = payload.get("data", []) if isinstance(payload, dict) else payload or []
    messages: list[dict] = []
    for row in reversed(rows):
        kind = row.get("type")
        created = (row.get("time") or {}).get("created")
        if kind == "user":
            text = row.get("text") or ""
            if text:
                messages.append({"id": row.get("id"), "role": "user", "text": text, "created": created})
        elif kind == "assistant":
            text = "\n".join(
                part.get("text", "") for part in row.get("content", []) if part.get("type") == "text"
            ).strip()
            if text:
                messages.append({"id": row.get("id"), "role": "assistant", "text": text, "created": created})
    return messages


async def interrupt(session_id: str) -> None:
    await _json("POST", f"/api/session/{session_id}/interrupt")


async def session_model(session_id: str) -> dict | None:
    """The model the session would use for the next prompt."""
    payload = await _json("GET", f"/api/session/{session_id}")
    row = payload.get("data", payload) if isinstance(payload, dict) else payload
    return model_ref((row or {}).get("model"))


def fallback_state() -> dict:
    return agent_fallback.policy.state()



def _sse(payload: dict) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


def _normalise(event: dict) -> dict | None:
    kind = event.get("type") or ""
    data = event.get("data") or {}
    session_id = data.get("sessionID")
    if not session_id:
        return None
    if kind == "session.text.delta":
        return {"type": "delta", "sessionID": session_id, "text": data.get("delta", "")}
    if kind == "session.text.started":
        return {"type": "text-start", "sessionID": session_id, "ordinal": data.get("ordinal", 0)}
    if kind == "session.text.ended":
        return {"type": "text", "sessionID": session_id, "text": data.get("text", "")}
    if kind == "session.tool.input.started":
        return {"type": "tool", "sessionID": session_id, "name": data.get("name") or "tool"}
    if kind == "session.tool.called":
        name = data.get("name") or data.get("tool") or data.get("toolID")
        return {"type": "tool", "sessionID": session_id, "name": name} if name else None
    if kind in ("session.tool.success", "session.tool.failed"):
        return {"type": "tool-done", "sessionID": session_id}
    if kind == "session.execution.started":
        return {"type": "started", "sessionID": session_id}
    if kind == "session.step.started":
        return {"type": "step", "sessionID": session_id, "agent": data.get("agent")}
    if kind in ("session.execution.failed", "session.step.failed"):
        message = data.get("error") or data.get("message") or "OpenCode stopped with an error"
        if isinstance(message, dict):
            message = message.get("message") or json.dumps(message)[:400]
        message = str(message)
        if "does not support tools" in message.lower():
            message = ("That model cannot use tools, so the coding agent cannot run with it. "
                       "Pick a tool-capable model in the Model list, for example "
                       "ollama/qwen2.5-coder:7b or opencode/deepseek-v4.1-flash-free.")
        return {"type": "error", "sessionID": session_id, "message": message}
    if kind == "session.execution.interrupted":
        return {"type": "interrupted", "sessionID": session_id}
    if kind == "session.execution.succeeded":
        return {"type": "done", "sessionID": session_id, "outcome": "succeeded"}
    return None


TERMINAL_EVENTS = {
    "session.execution.succeeded",
    "session.execution.failed",
    "session.execution.interrupted",
}


async def _pump_lines(lines: AsyncIterator[str], queue: "asyncio.Queue[tuple[str, Any]]") -> None:
    """Read the event stream in the background so the relay can send pings.

    Cancelling ``aiter_lines().__anext__`` directly would close the underlying
    response, so the reads live in their own task and the relay only waits on
    the queue.
    """
    try:
        async for line in lines:
            await queue.put(("line", line))
        await queue.put(("end", None))
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - surfaced as an SSE error frame
        await queue.put(("error", exc))


async def stream_chat(session_id: str, text: str) -> AsyncIterator[bytes]:
    """Stream one reply, replaying the prompt locally when the model is limited.

    The prompt is sent to the model the session already has. If that turn ends
    with a rate/quota error *before producing anything*, the same prompt is sent
    again on ``OPENCODE_FALLBACK_MODEL`` and the user sees a short notice. A
    cooldown then keeps the next messages on the local model, and once it
    expires the original model is tried again so a recovered quota is used
    automatically.
    """
    await ensure_server()
    local = agent_fallback.fallback_model()
    original = None
    switched = False
    if agent_fallback.enabled():
        try:
            original = await session_model(session_id)
        except BridgeError as exc:
            log.warning("Could not read the session model: %s", exc)
        if (original and local and not agent_fallback.same_model(original, local)
                and agent_fallback.policy.active()):
            # Still inside the cooldown window: do not waste a round trip on a
            # provider that already said it is out of quota.
            if await _try_set_model(session_id, local):
                switched = True
                yield _sse({"type": "notice", "sessionID": session_id,
                            "message": _notice(local, "Rate limit still active")})

    state: dict[str, Any] = {}
    async for chunk in _relay_turn(session_id, text, state, emit_accepted=True):
        yield chunk

    if state.get("completed") and not switched:
        agent_fallback.policy.clear()

    if (agent_fallback.enabled() and local and original
            and not switched
            and state.get("limit") and not state.get("produced")
            and not agent_fallback.same_model(original, local)):
        agent_fallback.policy.trigger(str(state.get("error") or ""))
        if await _try_set_model(session_id, local):
            switched = True
            yield _sse({"type": "notice", "sessionID": session_id,
                        "message": _notice(local, "The selected model hit a limit")})
            retry_state: dict[str, Any] = {}
            async for chunk in _relay_turn(session_id, text, retry_state, emit_accepted=False):
                yield chunk

    if switched and original:
        # Hand the chat back to the selected model. The next message probes it
        # again, which is how a recovered quota is picked up without polling.
        await _try_set_model(session_id, original)


def _notice(model: dict, prefix: str) -> str:
    return f"{prefix}. Continuing on {model.get('providerID')}/{model.get('id')}."


async def _try_set_model(session_id: str, model: dict) -> bool:
    try:
        await set_model(session_id, model)
        return True
    except BridgeError as exc:
        log.warning("Could not switch the session model: %s", exc)
        return False


async def _relay_turn(session_id: str, text: str, state: dict,
                      emit_accepted: bool) -> AsyncIterator[bytes]:
    """One prompt + event relay. ``state`` reports how the turn ended."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + STREAM_MAX_SECONDS
    stream = client().stream(
        "GET",
        "/api/event",
        headers={"Accept": "text/event-stream"},
        timeout=httpx.Timeout(STREAM_IDLE_TIMEOUT + 30, connect=10.0, read=None),
    )
    state.setdefault("accepted", False)
    state.setdefault("produced", False)
    state.setdefault("completed", False)
    state.setdefault("limit", False)
    state.setdefault("error", "")
    async with stream as response:
        if response.status_code >= 400:
            yield _sse({"type": "error", "message": f"OpenCode event stream failed ({response.status_code})"})
            return
        try:
            posted = await client().post(f"/api/session/{session_id}/prompt", json={"text": text})
            if posted.status_code >= 400:
                state["error"] = posted.text[:300]
                state["limit"] = agent_fallback.is_limit_error(posted.text)
                yield _sse({
                    "type": "error",
                    "message": f"OpenCode rejected the message ({posted.status_code}): {posted.text[:300]}",
                })
                return
        except httpx.HTTPError as exc:
            yield _sse({"type": "error", "message": f"Could not send the message: {exc}"})
            return

        if emit_accepted:
            yield _sse({"type": "accepted", "sessionID": session_id})
        queue: "asyncio.Queue[tuple[str, Any]]" = asyncio.Queue(maxsize=2000)
        pump = asyncio.create_task(_pump_lines(response.aiter_lines(), queue))
        last_event = loop.time()
        try:
            while True:
                if loop.time() > deadline:
                    yield _sse({"type": "error", "message": "This reply took too long and was stopped."})
                    return
                try:
                    kind, value = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    if loop.time() - last_event >= STREAM_IDLE_TIMEOUT:
                        yield _sse({"type": "error", "message": "OpenCode stopped responding."})
                        return
                    yield b": ping\n\n"
                    continue
                last_event = loop.time()
                if kind == "end":
                    yield _sse({"type": "error", "message": "OpenCode closed the event stream."})
                    return
                if kind == "error":
                    yield _sse({"type": "error", "message": f"OpenCode event stream failed: {value}"})
                    return
                line = value
                if not line.startswith("data:"):
                    continue
                try:
                    event = json.loads(line[5:].strip())
                except ValueError:
                    continue
                normalised = _normalise(event)
                if normalised is None:
                    continue
                if normalised["type"] in ("delta", "text", "tool"):
                    # Only real output blocks a fallback; a step/started frame
                    # is emitted before the provider is even called.
                    state["produced"] = True
                if normalised["type"] == "error":
                    state["error"] = normalised["message"]
                    state["limit"] = agent_fallback.is_limit_error(normalised["message"])
                if normalised["type"] == "done":
                    state["completed"] = True
                yield _sse(normalised)
                if event.get("type") in TERMINAL_EVENTS:
                    return
        finally:
            pump.cancel()
            try:
                await pump
            except (asyncio.CancelledError, Exception):
                pass

