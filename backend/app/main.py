"""FastAPI application entry point.

Configures:
- CORS middleware
- Rate limiting (SlowAPI)
- API routers
- Health check endpoint
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.api import auth, questions, answers


def create_limiter() -> Limiter:
    """Create a SlowAPI rate limiter."""
    return Limiter(key_func=get_remote_address)


limiter = create_limiter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks: log ready."""
    print("LabAssist backend started!")
    yield


app = FastAPI(
    title="LabAssist",
    description="AI-powered Q&A forum for lab courses",
    version="0.1.0",
    lifespan=lifespan,
)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Rate limiter ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# --- Health check ---
@app.get("/health")
@limiter.limit("10/minute")
async def health_check(request: Request):
    """Health check endpoint — no auth required."""
    return {"status": "ok", "version": "0.1.0"}


# --- Routers ---
app.include_router(auth.router, prefix="/api/v1")
app.include_router(questions.router, prefix="/api/v1")
app.include_router(answers.router, prefix="/api/v1")
