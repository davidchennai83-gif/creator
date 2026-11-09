"""Model fallback: a limited primary model must not end the chat."""
import json

import pytest

from app.config.settings import settings
from app.services import agent_fallback, opencode_bridge as bridge

PRIMARY = {"id": "deepseek-v4.1-flash-free", "providerID": "opencode"}
LOCAL = {"id": "qwen2.5-coder:7b", "providerID": "ollama"}


def _events(chunks):
    frames = []
    for block in b"".join(chunks).decode().split("\n\n"):
        if block.startswith("data:"):
            frames.append(json.loads(block[5:].strip()))
    return frames


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    agent_fallback.policy.clear()
    monkeypatch.setattr(settings, "OPENCODE_FALLBACK_MODEL", "ollama/qwen2.5-coder:7b")
    monkeypatch.setattr(settings, "OPENCODE_FALLBACK_COOLDOWN", 600)
    monkeypatch.setattr(bridge, "ensure_server", _noop)
    yield
    agent_fallback.policy.clear()


async def _noop(*args, **kwargs):
    return None


def _relay(scripts):
    """Fake one turn; each script is (state patch, frames)."""
    remaining = list(scripts)

    async def fake(session_id, text, state, emit_accepted):
        patch, frames = remaining.pop(0)
        if emit_accepted:
            yield bridge._sse({"type": "accepted", "sessionID": session_id})
        for frame in frames:
            yield bridge._sse(frame)
        state.update(patch)

    return fake


async def _run(monkeypatch, scripts, model=PRIMARY):
    switched = []

    async def fake_session_model(session_id):
        return model

    async def fake_set_model(session_id, ref):
        switched.append((ref["providerID"], ref["id"]))

    monkeypatch.setattr(bridge, "session_model", fake_session_model)
    monkeypatch.setattr(bridge, "set_model", fake_set_model)
    monkeypatch.setattr(bridge, "_relay_turn", _relay(scripts))
    chunks = [chunk async for chunk in bridge.stream_chat("ses_test", "hello")]
    return _events(chunks), switched


def test_limit_errors_are_recognised():
    assert agent_fallback.is_limit_error("429 Too Many Requests")
    assert agent_fallback.is_limit_error("You exceeded your current quota")
    assert agent_fallback.is_limit_error("Your credit balance is too low")
    assert agent_fallback.is_limit_error("monthly limit reached")
    assert agent_fallback.is_limit_error("Provider is overloaded")
    assert not agent_fallback.is_limit_error("registry.ollama.ai/library/x does not support tools")
    assert not agent_fallback.is_limit_error("invalid api key")
    assert not agent_fallback.is_limit_error(None)


def test_parse_ref_rejects_incomplete_values():
    assert agent_fallback.parse_ref("ollama/qwen2.5-coder:7b") == {
        "id": "qwen2.5-coder:7b", "providerID": "ollama"}
    assert agent_fallback.parse_ref("nonsense") is None
    assert agent_fallback.parse_ref("/model") is None
    assert agent_fallback.parse_ref("") is None


async def test_limit_before_output_replays_on_the_local_model(monkeypatch):
    scripts = [
        ({"error": "429 Too Many Requests", "limit": True},
         [{"type": "error", "sessionID": "ses_test", "message": "429 Too Many Requests"}]),
        ({"completed": True, "produced": True},
         [{"type": "delta", "sessionID": "ses_test", "text": "done locally"},
          {"type": "done", "sessionID": "ses_test", "outcome": "succeeded"}]),
    ]
    frames, switched = await _run(monkeypatch, scripts)

    assert any(frame["type"] == "notice" for frame in frames)
    assert any(frame.get("text") == "done locally" for frame in frames)
    # Once for the fallback, once to hand the session back to the selection.
    assert switched == [("ollama", "qwen2.5-coder:7b"), ("opencode", "deepseek-v4.1-flash-free")]
    assert agent_fallback.policy.active() is True


async def test_a_failure_after_output_is_not_replayed(monkeypatch):
    scripts = [
        ({"error": "429 rate limited", "limit": True, "produced": True},
         [{"type": "delta", "sessionID": "ses_test", "text": "partial"},
          {"type": "error", "sessionID": "ses_test", "message": "429 rate limited"}]),
    ]
    frames, switched = await _run(monkeypatch, scripts)

    assert switched == []
    assert [frame["type"] for frame in frames] == ["accepted", "delta", "error"]


async def test_cooldown_sends_the_next_message_straight_to_the_local_model(monkeypatch):
    agent_fallback.policy.trigger("429")
    scripts = [
        ({"completed": True},
         [{"type": "delta", "sessionID": "ses_test", "text": "local"},
          {"type": "done", "sessionID": "ses_test", "outcome": "succeeded"}]),
    ]
    frames, switched = await _run(monkeypatch, scripts)

    assert switched[0] == ("ollama", "qwen2.5-coder:7b")
    assert switched[-1] == ("opencode", "deepseek-v4.1-flash-free")
    notice = next(frame for frame in frames if frame["type"] == "notice")
    assert "still active" in notice["message"]


async def test_disabled_fallback_keeps_the_error(monkeypatch):
    monkeypatch.setattr(settings, "OPENCODE_FALLBACK_MODEL", "")
    scripts = [
        ({"error": "429 Too Many Requests", "limit": True},
         [{"type": "error", "sessionID": "ses_test", "message": "429 Too Many Requests"}]),
    ]
    frames, switched = await _run(monkeypatch, scripts)

    assert switched == []
    assert [frame["type"] for frame in frames] == ["accepted", "error"]


async def test_a_local_model_is_never_fallen_back_to_itself(monkeypatch):
    scripts = [
        ({"error": "quota exhausted", "limit": True},
         [{"type": "error", "sessionID": "ses_test", "message": "quota exhausted"}]),
    ]
    frames, switched = await _run(monkeypatch, scripts, model=LOCAL)

    assert switched == []
    assert not any(frame["type"] == "notice" for frame in frames)
