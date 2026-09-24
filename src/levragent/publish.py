from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import httpx

from .errors import PublishError

if TYPE_CHECKING:
    from .decorator import Agent

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
TOKEN_ENV_VAR = "LEVRAGENT_TOKEN"

# Header-scheme prefixes the SDK knows how to auto-format. The backend replays
# auth_value verbatim as the Authorization header (main.py), so an auth_type
# not listed here is sent through unprefixed rather than guessed at.
_AUTH_PREFIXES = {"bearer": "Bearer "}


def publish(
    agent: "Agent",
    endpoint_url: str,
    *,
    auth_type: str | None = None,
    auth_value: str | None = None,
    token: str | None = None,
    go_live: bool = True,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 30,
) -> dict:
    """Publish `agent` to the Levragent marketplace.

    `endpoint_url` is where this agent is reachable (local dev server or a
    deployed Lambda URL). `auth_type`/`auth_value` are the agent's own
    runtime auth, not the caller's credentials. `token` authenticates the
    publish call itself and falls back to the LEVRAGENT_TOKEN env var.
    """
    endpoint_url = _require_non_blank(endpoint_url, "endpoint_url")

    resolved_token = token or os.environ.get(TOKEN_ENV_VAR)
    if not resolved_token or not resolved_token.strip():
        raise PublishError(
            f"No auth token available: pass token=... or set the {TOKEN_ENV_VAR} "
            "environment variable."
        )

    payload = {
        "name": agent.name,
        "description": agent.description,
        "domain": agent.domain,
        "endpoint_url": endpoint_url,
        "auth_type": auth_type,
        "auth_value": _format_auth_value(auth_type, auth_value),
        "input_schema": agent.input_schema_dict(),
        "output_schema": agent.output_schema_dict(),
        "creator_name": agent.creator_name,
    }
    headers = {"Authorization": f"Bearer {resolved_token}"}

    try:
        response = httpx.post(
            f"{base_url}/agents/publish", json=payload, headers=headers, timeout=timeout
        )
    except httpx.HTTPError as exc:
        raise PublishError(f"Could not reach the Levragent backend at {base_url}: {exc}") from exc

    if not response.is_success:
        raise PublishError(f"Publishing '{agent.name}' failed: {_describe_error(response)}")

    created = response.json()

    if not go_live:
        return created

    agent_id = created["id"]
    try:
        publish_response = httpx.patch(
            f"{base_url}/agents/{agent_id}/publish", timeout=timeout
        )
    except httpx.HTTPError as exc:
        raise PublishError(
            f"'{agent.name}' was created as a draft (id={agent_id}) but going live failed: "
            f"could not reach the backend: {exc}"
        ) from exc

    if not publish_response.is_success:
        raise PublishError(
            f"'{agent.name}' was created as a draft (id={agent_id}) but going live failed: "
            f"{_describe_error(publish_response)}"
        )

    return publish_response.json()


def _require_non_blank(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublishError(f"{field_name} must not be blank")
    return value.strip()


def _format_auth_value(auth_type: str | None, auth_value: str | None) -> str | None:
    if not auth_type or auth_type.lower() == "none" or not auth_value:
        return auth_value
    prefix = _AUTH_PREFIXES.get(auth_type.lower(), "")
    if prefix and auth_value.startswith(prefix):
        return auth_value
    return f"{prefix}{auth_value}"


def _describe_error(response: Any) -> str:
    try:
        body = response.json()
        detail = body.get("detail") if isinstance(body, dict) else None
    except ValueError:
        detail = None
    message = detail or response.text or f"HTTP {response.status_code}"
    return f"{response.status_code} {message}"
