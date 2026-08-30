"""Deployment-only access guard for a public portfolio demo.

The regular application still owns persona and data-scope behavior.  This
middleware adds a narrow outer gate when ``DEMO_ACCESS_KEY`` is configured so
the backend URL cannot be called directly without going through the UI proxy.
"""

from __future__ import annotations

import hmac

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class DemoAccessMiddleware(BaseHTTPMiddleware):
    """Require ``X-Demo-Key`` outside public health checks when enabled."""

    def __init__(self, app, access_key: str | None = None):
        super().__init__(app)
        self._access_key = (access_key or "").strip()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not self._access_key or request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path == "/health" or path.startswith("/health/"):
            return await call_next(request)

        supplied_key = request.headers.get("x-demo-key", "")
        if not hmac.compare_digest(supplied_key, self._access_key):
            return JSONResponse(
                status_code=403,
                content={"detail": "This demo endpoint is accessible through the web app only."},
            )

        return await call_next(request)
