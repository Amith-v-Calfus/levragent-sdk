import importlib
import json

import httpx
import pytest
from pydantic import BaseModel

import levragent
from levragent.errors import PublishError

# levragent/__init__.py does `from .publish import publish`, which overwrites the
# `publish` attribute on the package with the function — so `import levragent.publish`
# would resolve to that function, not the submodule. Go through sys.modules instead.
publish_mod = importlib.import_module("levragent.publish")


class Input(BaseModel):
    city: str
    unit: str = "celsius"


class Output(BaseModel):
    temperature: float
    condition: str


@levragent.agent(
    input_schema=Input,
    output_schema=Output,
    description="Fake weather agent",
    domain="weather",
    creator_name="amith",
)
def run(input: Input) -> Output:
    return Output(temperature=21.5, condition="Sunny")


class FakeResponse:
    def __init__(self, status_code: int, json_body: dict):
        self.status_code = status_code
        self._json_body = json_body
        self.text = json.dumps(json_body)

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict:
        return self._json_body


@pytest.fixture(autouse=True)
def clear_token_env(monkeypatch):
    monkeypatch.delenv(publish_mod.TOKEN_ENV_VAR, raising=False)


def test_publish_sends_expected_payload_and_auth_header(monkeypatch):
    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return FakeResponse(200, {"id": "agent-1", "status": "draft"})

    def fake_patch(url, *, timeout):
        captured["patch_url"] = url
        return FakeResponse(200, {"id": "agent-1", "status": "published"})

    monkeypatch.setattr(publish_mod.httpx, "post", fake_post)
    monkeypatch.setattr(publish_mod.httpx, "patch", fake_patch)

    result = levragent.publish(run, "https://my-agent.example.com/run", token="creator-token")

    assert captured["url"] == f"{publish_mod.DEFAULT_BASE_URL}/agents/publish"
    assert captured["headers"] == {"Authorization": "Bearer creator-token"}
    assert captured["json"] == {
        "name": "run",
        "description": "Fake weather agent",
        "domain": "weather",
        "endpoint_url": "https://my-agent.example.com/run",
        "auth_type": None,
        "auth_value": None,
        "input_schema": {"city": "str"},
        "output_schema": {"temperature": "float", "condition": "str"},
        "creator_name": "amith",
    }
    assert captured["patch_url"] == f"{publish_mod.DEFAULT_BASE_URL}/agents/agent-1/publish"
    assert result == {"id": "agent-1", "status": "published"}


def test_publish_go_live_false_skips_the_patch_call(monkeypatch):
    patch_called = False

    def fake_post(url, *, json, headers, timeout):
        return FakeResponse(200, {"id": "agent-1", "status": "draft"})

    def fake_patch(url, *, timeout):
        nonlocal patch_called
        patch_called = True
        return FakeResponse(200, {})

    monkeypatch.setattr(publish_mod.httpx, "post", fake_post)
    monkeypatch.setattr(publish_mod.httpx, "patch", fake_patch)

    result = levragent.publish(
        run, "https://my-agent.example.com/run", token="creator-token", go_live=False
    )

    assert patch_called is False
    assert result == {"id": "agent-1", "status": "draft"}


def test_publish_auto_prefixes_bearer_auth_value(monkeypatch):
    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured["json"] = json
        return FakeResponse(200, {"id": "agent-1"})

    monkeypatch.setattr(publish_mod.httpx, "post", fake_post)
    monkeypatch.setattr(publish_mod.httpx, "patch", lambda url, timeout: FakeResponse(200, {}))

    levragent.publish(
        run,
        "https://my-agent.example.com/run",
        token="creator-token",
        auth_type="bearer",
        auth_value="sk-abc",
    )

    assert captured["json"]["auth_type"] == "bearer"
    assert captured["json"]["auth_value"] == "Bearer sk-abc"


def test_publish_does_not_double_prefix_an_already_formatted_bearer_value(monkeypatch):
    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured["json"] = json
        return FakeResponse(200, {"id": "agent-1"})

    monkeypatch.setattr(publish_mod.httpx, "post", fake_post)
    monkeypatch.setattr(publish_mod.httpx, "patch", lambda url, timeout: FakeResponse(200, {}))

    levragent.publish(
        run,
        "https://my-agent.example.com/run",
        token="creator-token",
        auth_type="bearer",
        auth_value="Bearer sk-abc",
    )

    assert captured["json"]["auth_value"] == "Bearer sk-abc"


def test_publish_leaves_non_bearer_auth_value_untouched(monkeypatch):
    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured["json"] = json
        return FakeResponse(200, {"id": "agent-1"})

    monkeypatch.setattr(publish_mod.httpx, "post", fake_post)
    monkeypatch.setattr(publish_mod.httpx, "patch", lambda url, timeout: FakeResponse(200, {}))

    levragent.publish(
        run,
        "https://my-agent.example.com/run",
        token="creator-token",
        auth_type="api_key",
        auth_value="xyz",
    )

    assert captured["json"]["auth_value"] == "xyz"


def test_publish_rejects_blank_endpoint_url_without_any_network_call(monkeypatch):
    calls = []
    monkeypatch.setattr(publish_mod.httpx, "post", lambda *a, **k: calls.append("post"))
    monkeypatch.setattr(publish_mod.httpx, "patch", lambda *a, **k: calls.append("patch"))

    with pytest.raises(PublishError, match="endpoint_url must not be blank"):
        levragent.publish(run, "   ", token="creator-token")

    assert calls == []


def test_publish_uses_env_var_token_when_not_passed_explicitly(monkeypatch):
    monkeypatch.setenv(publish_mod.TOKEN_ENV_VAR, "env-token")
    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured["headers"] = headers
        return FakeResponse(200, {"id": "agent-1"})

    monkeypatch.setattr(publish_mod.httpx, "post", fake_post)
    monkeypatch.setattr(publish_mod.httpx, "patch", lambda url, timeout: FakeResponse(200, {}))

    levragent.publish(run, "https://my-agent.example.com/run")

    assert captured["headers"] == {"Authorization": "Bearer env-token"}


def test_publish_raises_when_no_token_available_anywhere(monkeypatch):
    calls = []
    monkeypatch.setattr(publish_mod.httpx, "post", lambda *a, **k: calls.append("post"))

    with pytest.raises(PublishError, match="No auth token available"):
        levragent.publish(run, "https://my-agent.example.com/run")

    assert calls == []


def test_publish_raises_a_clear_error_on_backend_rejection(monkeypatch):
    def fake_post(url, *, json, headers, timeout):
        return FakeResponse(400, {"detail": "name must not be blank"})

    monkeypatch.setattr(publish_mod.httpx, "post", fake_post)

    with pytest.raises(PublishError, match="name must not be blank"):
        levragent.publish(run, "https://my-agent.example.com/run", token="creator-token")


def test_publish_raises_when_backend_is_unreachable(monkeypatch):
    def fake_post(url, *, json, headers, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(publish_mod.httpx, "post", fake_post)

    with pytest.raises(PublishError, match="Could not reach the Levragent backend"):
        levragent.publish(run, "https://my-agent.example.com/run", token="creator-token")


def test_publish_raises_when_go_live_patch_fails_after_draft_is_created(monkeypatch):
    def fake_post(url, *, json, headers, timeout):
        return FakeResponse(200, {"id": "agent-1"})

    def fake_patch(url, *, timeout):
        return FakeResponse(500, {"detail": "internal error"})

    monkeypatch.setattr(publish_mod.httpx, "post", fake_post)
    monkeypatch.setattr(publish_mod.httpx, "patch", fake_patch)

    with pytest.raises(PublishError, match="was created as a draft"):
        levragent.publish(run, "https://my-agent.example.com/run", token="creator-token")


def test_agent_publish_method_delegates_to_module_level_publish(monkeypatch):
    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured["json"] = json
        return FakeResponse(200, {"id": "agent-1"})

    monkeypatch.setattr(publish_mod.httpx, "post", fake_post)

    result = run.publish("https://my-agent.example.com/run", token="creator-token", go_live=False)

    assert result == {"id": "agent-1"}
    assert captured["json"]["endpoint_url"] == "https://my-agent.example.com/run"
