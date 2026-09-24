from __future__ import annotations

import base64
import json
from typing import Any, Callable

from .decorator import Agent


def make_handler(agent: Agent) -> Callable[[dict, Any], dict]:
    """Build an AWS Lambda entrypoint for `agent`.

    Feeds the same Agent.handle_request() core logic used by server.py,
    adapted to API Gateway / Lambda Function URL's event/response shape.
    """

    def handler(event: dict, context: Any = None) -> dict:
        raw_body = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            raw_body = base64.b64decode(raw_body).decode("utf-8")

        try:
            payload = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            status_code, response_body = 400, {
                "error": {"type": "invalid_json", "message": "Request body was not valid JSON"}
            }
        else:
            status_code, response_body = agent.handle_request(payload)

        return {
            "statusCode": status_code,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(response_body),
        }

    return handler
