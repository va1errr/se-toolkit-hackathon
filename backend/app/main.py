"""FastAPI application entry point.

Configures:
- Structured logging (structlog)
- CORS middleware
- Request logging middleware
- Global error handling
- Rate limiting (SlowAPI)
- API routers
- Health check endpoint
"""

import traceback
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.api import auth, questions, answers
from app.middleware import RequestLoggingMiddleware
from app.services.logging import setup_logging


def create_limiter() -> Limiter:
    """Create a SlowAPI rate limiter."""
    return Limiter(key_func=get_remote_address)


limiter = create_limiter()
logger = structlog.get_logger()


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler for unhandled errors.

    Logs the full traceback server-side but returns a clean error message
    to the client (no stack traces leaked).
    """
    logger.error(
        "unhandled_exception",
        method=request.method,
        path=request.url.path,
        error_type=type(exc).__name__,
        error_message=str(exc),
        traceback=traceback.format_exc(),
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred. Please try again later.",
        },
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks: configure logging, log ready."""
    setup_logging()
    logger.info("LabAssist backend started", version="0.1.0", env=settings.app_env)
    yield


app = FastAPI(
    title="LabAssist",
    description="AI-powered Q&A forum for lab courses",
    version="0.1.0",
    lifespan=lifespan,
)

# --- Global exception handler (catches everything not handled elsewhere) ---
app.add_exception_handler(Exception, global_exception_handler)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging (must be added AFTER CORS, BEFORE routers)
app.add_middleware(RequestLoggingMiddleware)

# --- Rate limiter ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# --- Health check ---
@app.get("/health")
@limiter.limit("10/minute")
async def health_check(request: Request):
    """Health check endpoint — no auth required."""
    logger.debug("health_check_requested")
    return {"status": "ok", "version": "0.1.0"}


# --- Routers ---
app.include_router(auth.router, prefix="/api/v1")
app.include_router(questions.router, prefix="/api/v1")
app.include_router(answers.router, prefix="/api/v1")
