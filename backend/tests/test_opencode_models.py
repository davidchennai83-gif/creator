"""OpenCode model catalogue: never offer a model the tool-using agent cannot run."""
from app.services import opencode_bridge as bridge


async def test_list_models_hides_models_without_tool_support(monkeypatch):
    payload = {"data": [
        {"modelID": "qwen2.5-coder:7b", "providerID": "ollama", "name": "Qwen2.5 Coder",
         "capabilities": {"tools": True}, "cost": []},
        {"modelID": "deepseek-coder-v2:latest", "providerID": "ollama",
         "name": "deepseek-coder-v2:latest", "capabilities": {"tools": False}, "cost": []},
        {"modelID": "no-capabilities", "providerID": "opencode", "name": "Unknown",
         "cost": [{"input": 0, "output": 0}]},
    ]}

    async def fake_json(method, path, **kwargs):
        assert (method, path) == ("GET", "/api/model")
        return payload

    monkeypatch.setattr(bridge, "_json", fake_json)
    listing = await bridge.list_models()

    ids = [model["id"] for model in listing["models"]]
    assert "deepseek-coder-v2:latest" not in ids
    assert ids == ["qwen2.5-coder:7b", "no-capabilities"]
    assert all(model["tools"] is True for model in listing["models"])
    assert listing["default"]["id"] in ids


def test_normalise_explains_a_model_without_tools():
    event = {
        "type": "session.execution.failed",
        "data": {
            "sessionID": "ses_1",
            "error": "registry.ollama.ai/library/deepseek-coder-v2:latest does not support tools",
        },
    }
    frame = bridge._normalise(event)
    assert frame["type"] == "error"
    assert "cannot use tools" in frame["message"]
    assert "qwen2.5-coder" in frame["message"]
