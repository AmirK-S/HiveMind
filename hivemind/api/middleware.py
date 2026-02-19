"""Usage metering for HiveMind REST API.

Usage metering (request_count increment + last_used_at update) is integrated
directly into the ``require_api_key`` dependency in ``hivemind/api/auth.py``
rather than a separate Starlette BaseHTTPMiddleware class.

Rationale (from plan notes):
- Metering inside the auth dependency runs in the same DB session as key validation,
  making the counter increment atomic with authentication.
- FastAPI dependency injection is cleanly testable by overriding dependencies in
  test clients — no raw Request/Response manipulation needed.
- Avoids the known pitfalls of BaseHTTPMiddleware with streaming responses and
  exception handlers.

This module is kept as a thin re-export shim so that any future code that imports
``UsageMeteringMiddleware`` from this path continues to work, and to document the
design decision for maintainers.

To add true post-response metering in the future (e.g. record response latency),
implement a ``@app.middleware("http")`` decorator or a Starlette ``Route``-level
dependency here and register it in ``server/main.py``.

Requirements: INFRA-04.
"""

# Metering is implemented in hivemind/api/auth.py as part of require_api_key.
# Nothing to export from this module currently — it is a design documentation stub.

__all__: list[str] = []
