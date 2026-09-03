"""Optional shared-token authentication for mutating API routes."""

import hmac

from fastapi import Header, HTTPException

from ai_daily.config import config


def require_api_token(authorization: str | None = Header(default=None)) -> None:
    """Reject the request unless it carries the configured bearer token.

    When API_TOKEN is unset the check is skipped, which keeps local development
    and the loopback-only Docker setup frictionless.
    """
    expected = config.api_token
    if not expected:
        return
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid API token")
