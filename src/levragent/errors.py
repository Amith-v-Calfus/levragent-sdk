from __future__ import annotations


class LevragentError(Exception):
    """Base class for all errors raised directly by the SDK."""


class PublishError(LevragentError):
    """Raised when publish() can't reach, or is rejected by, the backend."""


def error_body(error_type: str, message: str, *, errors: list | None = None) -> dict:
    body = {"success": False, "error": {"type": error_type, "message": message}}
    if errors is not None:
        body["error"]["details"] = errors
    return body
