"""Request logging middleware.

Logs every HTTP request with:
- Method and path
- Response status code
- Request duration in milliseconds
"""

import time
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with timing information."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.monotonic()
        response: Response | None = None
        status_code = 500  # Default if something fails before response

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # Let the global exception handler deal with it
            raise
        finally:
            duration_ms = (time.monotonic() - start_time) * 1000

            # Skip logging health checks to reduce noise
            if request.url.path != "/health":
                logger.info(
                    "http_request",
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    duration_ms=round(duration_ms, 1),
                )

        return response  # type: ignore[return-value]
