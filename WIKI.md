# LabAssist — Complete Technical Wiki

This document is the single source of truth for **everything** about LabAssist. It is written to be understandable by beginners while maintaining the technical depth that experienced developers expect. Every aspect of the implementation is covered here.

---

## Table of Contents

### Getting Started
1. [What Is LabAssist?](#1-what-is-labassist)
2. [System Requirements](#2-system-requirements)
3. [First-Time Setup](#3-first-time-setup)

### Architecture
4. [Overall Architecture](#4-overall-architecture)
5. [Component Diagram](#5-component-diagram)
6. [Data Flow](#6-data-flow)
7. [Request Lifecycle](#7-request-lifecycle)

### Backend
8. [FastAPI Application Structure](#8-fastapi-application-structure)
9. [Configuration System](#9-configuration-system)
10. [Database Layer](#10-database-layer)
11. [API Endpoints](#11-api-endpoints)
12. [Authentication & Authorization](#12-authentication--authorization)
13. [Middleware](#13-middleware)
14. [Error Handling](#14-error-handling)
15. [Logging](#15-logging)
16. [Rate Limiting](#16-rate-limiting)

### AI & RAG System
17. [What Is RAG?](#17-what-is-rag)
18. [How LabAssist Uses RAG](#18-how-labassist-uses-rag)
19. [Embedding System](#19-embedding-system)
20. [Document Chunking](#20-document-chunking)
21. [Vector Search (pgvector)](#21-vector-search-pgvector)
22. [Retrieval Logic](#22-retrieval-logic)
23. [Prompt Engineering](#23-prompt-engineering)
24. [LLM Integration](#24-llm-integration)
25. [Response Parsing](#25-response-parsing)
26. [Background Task Processing](#26-background-task-processing)
27. [What Is qwen-code-api?](#27-what-is-qwen-code-api)
28. [How RAG Connects with qwen-code-api](#28-how-rag-connects-with-qwen-code-api)

### Database
29. [Database Schema](#29-database-schema)
30. [Migrations (Alembic)](#30-migrations-alembic)
31. [Seeding](#31-seeding)
32. [Vector Embeddings in PostgreSQL](#32-vector-embeddings-in-postgresql)

### Frontend
33. [Frontend Architecture](#33-frontend-architecture)
34. [Page Components](#34-page-components)
35. [Shared Components](#35-shared-components)
36. [State Management](#36-state-management)
37. [API Client](#37-api-client)
38. [Routing](#38-routing)
39. [Styling](#39-styling)

### Infrastructure
40. [Docker Setup](#40-docker-setup)
41. [Development vs Production](#41-development-vs-production)
42. [Reverse Proxy (Nginx)](#42-reverse-proxy-nginx)
43. [Environment Variables](#43-environment-variables)

### Development
44. [Local Development Setup](#44-local-development-setup)
45. [Debugging](#45-debugging)
46. [Testing](#46-testing)
47. [Database Migrations Guide](#47-database-migrations-guide)

### Operations
48. [Deployment](#48-deployment)
49. [Backup & Restore](#49-backup--restore)
50. [Monitoring & Health Checks](#50-monitoring--health-checks)
51. [Updating the Application](#51-updating-the-application)

### Troubleshooting & FAQ
52. [Common Issues](#52-common-issues)
53. [Known Limitations](#53-known-limitations)
54. [Edge Cases](#54-edge-cases)
55. [FAQ](#55-faq)

### Reference
56. [Tools & Dependencies](#56-tools--dependencies)
57. [Design Decisions](#57-design-decisions)
58. [File Reference](#58-file-reference)

---

## 1. What Is LabAssist?

LabAssist is a web application that serves as an **AI-powered Q&A forum** for students taking programming lab courses. Here's the core problem it solves:

> A student is working on a lab assignment and gets stuck. Normally, they'd have to wait for a TA to become available — which could take hours. With LabAssist, they post their question and get an **instant AI-generated answer** based on the course's lab materials. If the AI isn't confident, the question goes to a TA review queue.

The key differentiator from a regular forum is the **RAG (Retrieval-Augmented Generation) pipeline**: instead of the AI making things up, it retrieves actual course materials and bases its answers on them.

---

## 2. System Requirements

### Minimum Requirements
- **Docker** v24+ (with Compose v2+)
- **2 GB RAM** (for the embedding model + PostgreSQL)
- **5 GB disk** (Docker images + model cache)
- **CPU** — no GPU required (embedding model runs on CPU)

### For Production
- **4 GB RAM recommended** (for comfortable operation under load)
- **Domain name** (optional — for HTTPS via external reverse proxy or load balancer)
- **Open ports 80 and 443**

---

## 3. First-Time Setup

If you've never worked with this project before, here's the exact sequence:

```bash
# 1. Clone
git clone <repo-url>
cd LabAssist

# 2. Environment setup
cp .env.example .env
# Edit .env — at minimum set LLM_API_BASE and generate a SECRET_KEY

# 3. Start Qwen Code API proxy (if not already running)
cd qwen-code-api && cp .env.example .env && docker compose up -d --build
cd ..

# 4. Start LabAssist
docker compose up -d --build

# 5. Seed database
docker compose exec backend python -m seed

# 6. Open browser → http://localhost
# Login: admin / admin123
```

---

## 4. Overall Architecture

LabAssist follows a **three-tier architecture**:

```
┌──────────────┐        ┌──────────────────┐        ┌───────────┐
│   Frontend   │  REST  │     Backend      │  HTTP  │  LLM API  │
│  React 18    │───────►│   FastAPI 0.115  │───────►│  (Qwen)   │
│  TypeScript  │  /api  │   Python 3.12    │  /v1   │  proxy    │
└──────────────┘        │                  │        └───────────┘
                        │  ┌─────────────┐ │
                        │  │   RAG       │ │
                        │  │  Pipeline   │ │
                        │  └──────┬──────┘ │
                        └─────────┼────────┘
                                  │
                         ┌────────▼────────┐
                         │   PostgreSQL    │
                         │   + pgvector    │
                         └─────────────────┘
```

**The three tiers are:**

1. **Presentation tier** (Frontend): React SPA that users interact with. Served by Vite in dev, Nginx in production.
2. **Application tier** (Backend): FastAPI server that handles all business logic, database access, and AI processing.
3. **Data tier** (Database + LLM): PostgreSQL stores all data (including vector embeddings), and the LLM API generates answers.

**Key design principle**: The frontend knows nothing about the database or the LLM. It only talks to the backend via REST API. The backend orchestrates everything.

---

## 5. Component Diagram

Here's every component and what it does:

### Frontend Components
| Component | File | Purpose |
|-----------|------|---------|
| `App` | `App.tsx` | Router setup, protected routes, wraps everything in AuthProvider |
| `AuthContext` | `context/AuthContext.tsx` | Manages user session (login, register, logout, token storage) |
| `Navbar` | `components/Navbar.tsx` | Top navigation bar with role-aware links |
| `QuestionCard` | `components/QuestionCard.tsx` | Summary card for the questions list |
| `AnswerCard` | `components/AnswerCard.tsx` | Full answer display with rating, editing, deletion |
| API Client | `api/client.ts` | Axios instance with automatic JWT attachment |

### Backend Components
| Component | File | Purpose |
|-----------|------|---------|
| `app` | `main.py` | FastAPI application factory, middleware, router registration |
| `config` | `config.py` | pydantic-settings Settings singleton (env var loading) |
| `database` | `database.py` | Async + sync SQLAlchemy engines, session dependency |
| `models` | `models/models.py` | SQLModel table definitions (User, Question, Answer, Rating, LabDoc) |
| `schemas` | `models/schemas.py` | Pydantic request/response validation schemas |
| `auth API` | `api/auth.py` | Register and login endpoints |
| `questions API` | `api/questions.py` | Question CRUD + semantic search + background AI answer |
| `answers API` | `api/answers.py` | TA answer creation + answer rating |
| `ta_review API` | `api/ta_review.py` | TA review queue + answer edit/delete + question hide/unhide |
| `stats API` | `api/stats.py` | Forum analytics |
| `auth service` | `services/auth.py` | Password hashing (bcrypt) + JWT creation/validation |
| `dependencies` | `services/dependencies.py` | `get_current_user`, `require_role()` FastAPI dependencies |
| `rag` | `services/rag.py` | Full RAG pipeline (embed → retrieve → generate → parse) |
| `embeddings` | `services/embeddings.py` | EmbeddingService singleton (sentence-transformers wrapper) |
| `chunker` | `services/chunker.py` | Splits large markdown into chunks at heading boundaries |
| `logging` | `services/logging.py` | structlog configuration (JSON prod / console dev) |
| `middleware` | `middleware.py` | Request logging (method, path, status, duration) |

### Infrastructure Components
| Component | File | Purpose |
|-----------|------|---------|
| `docker-compose.yml` | Root | Dev stack: postgres (5433), backend (8000), frontend (80→5173) |
| `docker-compose.prod.yml` | Root | Prod stack: optimized builds, health checks, restart policies |
| `Dockerfile` (backend) | `backend/` | Dev: Python 3.12-slim, hot-reload |
| `Dockerfile.prod` (backend) | `backend/` | Prod: 2 uvicorn workers, no hot-reload |
| `Dockerfile` (frontend) | `frontend/` | Dev: Node 20, Vite dev server |
| `Dockerfile.prod` (frontend) | `frontend/` | Prod: Nginx serving built static files |

---

## 6. Data Flow

### Question Submission Flow

```
User types question → Frontend POSTs to /api/v1/questions
    ↓
Backend creates Question record with status="analyzing"
    ↓
Backend returns QuestionResponse to frontend immediately
    ↓
Frontend navigates to question detail page
    ↓
Frontend starts polling every 2 seconds (is the AI answer ready?)
    ↓
[Background] FastAPI BackgroundTask runs _generate_ai_answer():
    1. Embed question text → 384-dim vector
    2. Search lab_doc table via pgvector cosine similarity
    3. Build prompt with retrieved context
    4. Call LLM API
    5. Parse answer text + confidence from response
    6. Create Answer record (source="ai")
    7. Update Question: status = "answered" or "open", set ai_answer_id
    ↓
[Next poll] Frontend detects AI answer → displays it
    ↓
User rates answer 👍 or 👎 → POST to /api/v1/answers/{id}/rate
    ↓
If 👎 on AI answer → question appears in TA Queue
    ↓
TA sees flagged answer → adds corrected answer → question status = "answered"
```

### Semantic Search Flow (Duplicate Detection)

```
User types question title (≥5 chars)
    ↓
Frontend debounces 500ms → GET /api/v1/questions/search?q=title
    ↓
Backend embeds search query → pgvector similarity search
    ↓
Returns top 5 questions with similarity scores
    ↓
Frontend filters to >30% similarity → shows suggestions
    ↓
User sees "🔍 Similar questions: ..." with links and match percentages
```

---

## 7. Request Lifecycle

Every HTTP request goes through this lifecycle:

1. **Nginx** (in frontend container, production) or **Vite proxy** (development) receives the request
2. **CORS middleware** checks the origin against `settings.cors_origins_list`
3. **RequestLoggingMiddleware** starts a timer, logs method + path when complete
4. **FastAPI router** matches the path to an endpoint handler
5. **Dependency injection** runs:
   - `get_session()` → opens async database transaction
   - `get_current_user()` or `require_role()` → validates JWT token
6. **Endpoint handler** executes business logic (query DB, call RAG, etc.)
7. **Response serialization** — Pydantic schema validates and serializes the response
8. **Transaction commit** — `get_session` yields, then commits (or rolls back on error)
9. **RequestLoggingMiddleware** logs status code + duration_ms
10. **Global exception handler** catches any unhandled errors → returns clean 500 response

---

## 8. FastAPI Application Structure

The application is created in `main.py` using a factory pattern:

```python
app = FastAPI(
    title="LabAssist",
    description="AI-powered Q&A forum for lab courses",
    version="0.1.0",
    lifespan=lifespan,  # Startup: configure logging
)
```

**Middleware stack** (order matters — added in this sequence):
1. CORS middleware (FastAPI built-in)
2. RequestLoggingMiddleware (custom)

**Exception handlers**:
- Global `Exception` handler → logs traceback, returns clean 500
- `RateLimitExceeded` handler → SlowAPI's default

**Routers** (mounted with `/api/v1` prefix):
- `auth` → `/api/v1/auth/*`
- `questions` → `/api/v1/questions/*`
- `answers` → `/api/v1/questions/{id}/answer`, `/api/v1/answers/{id}/rate`
- `ta_review` → `/api/v1/ta/*`, `/api/v1/answers/{id}`, `/api/v1/questions/{id}/hide`
- `stats` → `/api/v1/stats`

**Startup** (`lifespan`): Calls `setup_logging()` to configure structlog.

---

## 9. Configuration System

All configuration lives in `backend/app/config.py`. It uses **pydantic-settings**, which automatically reads environment variables and `.env` files.

### How It Works

```python
class Settings(BaseSettings):
    database_url: str = Field(default="postgresql+asyncpg://...")
    llm_api_base: str = Field(default="https://api.qwen.ai/v1")
    # ... more fields

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),        # Reads from .env file
        env_file_encoding="utf-8",
        case_sensitive=False,           # DATABASE_URL = database_url
    )

settings = Settings()  # Singleton — import from anywhere
```

### Priority Order (highest to lowest)
1. Environment variables (e.g., `export DATABASE_URL=...`)
2. Values in the `.env` file (one directory level up from `backend/`)
3. Default values in the Field definitions

### Computed Properties

Some settings are computed dynamically:

```python
@property
def sync_database_url(self) -> str:
    # Changes +asyncpg to psycopg2 for sync connections (Alembic, seeding)
    return self.database_url.replace("+asyncpg", "").replace(
        "postgresql://", "postgresql+psycopg2://"
    )

@property
def cors_origins_list(self) -> List[str]:
    # Splits comma-separated string into a list
    return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
```

### Why This Matters

- **Never hardcode URLs or secrets** — everything goes through `settings`
- **Alembic and seed scripts** use `sync_database_url` (psycopg2) while the app uses `database_url` (asyncpg)
- **CORS** accepts a comma-separated string in `.env` but the app needs a list — `cors_origins_list` handles the conversion

---

## 10. Database Layer

### Two Engines

The app needs **two** database engines because FastAPI is async but Alembic is sync:

```python
# Async engine — used by FastAPI request handlers
async_engine = create_async_engine(
    settings.database_url,           # postgresql+asyncpg://...
    echo=settings.app_env == "development",  # Log SQL in dev
)
AsyncSessionLocal = sessionmaker(bind=async_engine, class_=AsyncSession)

# Sync engine — used by Alembic migrations and seed scripts
sync_engine = create_engine(settings.sync_database_url)  # postgresql+psycopg2://...
```

### The `get_session` Dependency

This is a **FastAPI dependency** that every endpoint uses:

```python
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()      # Auto-commit on success
        except Exception:
            await session.rollback()    # Auto-rollback on error
            raise
```

**Usage in endpoints:**
```python
async def create_question(session: AsyncSession = Depends(get_session)):
    # session is already open, will auto-commit when function returns
```

**Why this pattern?** Every request gets its own transaction. If the handler succeeds, the transaction commits. If it raises an exception, it rolls back. This prevents half-committed data.

---

## 11. API Endpoints

### Complete Endpoint Reference

#### Health
| | |
|---|---|
| **Method** | `GET` |
| **Path** | `/health` |
| **Auth** | None |
| **Rate Limit** | 10/minute |
| **Response** | `{"status": "ok", "version": "0.1.0"}` |

#### Authentication
| | |
|---|---|
| **POST** | `/api/v1/auth/register` |
| **Body** | `{"username": str, "password": str, "role": "student" (optional)}` |
| **Response** | User object `{"id", "username", "role", "created_at"}` |
| **Errors** | 400 if username exists |

| | |
|---|---|
| **POST** | `/api/v1/auth/login` |
| **Body** | `{"username": str, "password": str}` |
| **Response** | `{"access_token": str, "token_type": "bearer"}` |
| **Errors** | 401 if credentials invalid |

#### Questions
| | |
|---|---|
| **POST** | `/api/v1/questions` |
| **Auth** | Required (any role) |
| **Body** | `{"title": str, "body": str}` |
| **Response** | QuestionResponse `{"id", "user_id", "title", "body", "status": "analyzing", ...}` |
| **Behavior** | Creates question → schedules AI background task → returns immediately |

| | |
|---|---|
| **GET** | `/api/v1/questions` |
| **Auth** | None (public) |
| **Query Params** | `status` (optional filter), `skip` (pagination offset), `limit` (1-100, default 20) |
| **Response** | Array of QuestionResponse with computed `answer_label` field |

| | |
|---|---|
| **GET** | `/api/v1/questions/search` |
| **Auth** | None (public) |
| **Query Params** | `q` (search text, min 3 chars), `top_k` (1-20, default 5) |
| **Response** | Array with `similarity` score added |

| | |
|---|---|
| **GET** | `/api/v1/questions/{id}` |
| **Auth** | Optional (unauthenticated users can view, authenticated users see their own rating) |
| **Response** | QuestionDetail with full answers array, rating counts, and `user_rating` |

#### Answers
| | |
|---|---|
| **POST** | `/api/v1/questions/{id}/answer` |
| **Auth** | Required, TA+ role |
| **Body** | `{"body": str}` |
| **Response** | AnswerResponse `{"id", "question_id", "user_id", "body", "source": "ta", ...}` |

| | |
|---|---|
| **POST** | `/api/v1/answers/{id}/rate` |
| **Auth** | Required (any role) |
| **Body** | `{"helpful": bool}` |
| **Response** | RatingResponse |
| **Behavior** | If a non-AI answer gets its first 👍, question status → "answered". If a TA answer loses its last 👍, question status → "open" |

#### TA Review
| | |
|---|---|
| **GET** | `/api/v1/ta/flagged` |
| **Auth** | Required, TA+ role |
| **Response** | Array of flagged items: question + AI answer + rating counts |
| **Logic** | Returns AI answers with ≥1 👎 OR status="open" (low confidence), excluding questions that already have a TA answer with ≥1 👍 |

| | |
|---|---|
| **POST** | `/api/v1/ta/questions/{id}/answer` |
| **Auth** | Required, TA+ role |
| **Behavior** | Adds TA answer → question auto-removed from flagged list when it gets a 👍 |

| | |
|---|---|
| **PUT** | `/api/v1/answers/{id}` |
| **Auth** | Required. TA can edit own. Admin can edit any non-AI. |
| **Behavior** | Sets `edited=True` on the answer |

| | |
|---|---|
| **DELETE** | `/api/v1/answers/{id}` |
| **Auth** | Required. TA can delete own. Admin can delete any non-AI. |
| **Behavior** | Also deletes all ratings for the answer (FK constraint) |

| | |
|---|---|
| **PUT** | `/api/v1/questions/{id}/hide` |
| **Auth** | Required, Admin only |
| **Behavior** | Soft-hides question from TA queue (sets `hidden=True`) |

| | |
|---|---|
| **PUT** | `/api/v1/questions/{id}/unhide` |
| **Auth** | Required, Admin only |
| **Behavior** | Unhides question (sets `hidden=False`) |

#### Stats
| | |
|---|---|
| **GET** | `/api/v1/stats` |
| **Auth** | Optional |
| **Response** | Comprehensive analytics: question counts, AI performance, ratings, top users |

---

## 12. Authentication & Authorization

### Password Hashing

Passwords are hashed with **bcrypt** using the `bcrypt` Python package (not passlib):

```python
import bcrypt

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
```

**Why bcrypt?** It's a slow, adaptive hashing function designed for passwords. Each hash generates a random salt, so the same password produces different hashes — preventing rainbow table attacks.

### JWT Tokens

Tokens are created with **PyJWT** using HS256 (HMAC with SHA-256):

```python
def create_access_token(user_id: UUID, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    payload = {
        "sub": str(user_id),     # Subject = user ID
        "role": role,            # User role (student/ta/admin)
        "exp": expire,           # Expiration time
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")
```

**Token structure**: A JWT has three parts separated by dots: `header.payload.signature`. The payload is base64-encoded JSON. You can decode it with `atob()` in the browser (which is how the frontend extracts user info).

### Role Hierarchy

Roles are ordered numerically:
- `student` = 0
- `ta` = 1
- `admin` = 2

The `require_role()` factory creates a dependency that checks this hierarchy:

```python
def require_role(minimum_role: str):
    role_hierarchy = {"student": 0, "ta": 1, "admin": 2}
    minimum_level = role_hierarchy[minimum_role]

    async def role_checker(user: User = Depends(get_required_user)):
        if role_hierarchy[user.role] < minimum_level:
            raise HTTPException(status_code=403, detail="Requires '{minimum_role}' role or higher")
        return user

    return role_checker
```

**Usage**: `Depends(require_role("ta"))` means the user must be a TA or admin. A student (level 0) would get a 403 error.

### Optional vs Required Auth

- `get_current_user` → returns `User | None` (used for public endpoints that want to know who's logged in)
- `get_required_user` → raises 401 if not authenticated (used for protected endpoints)

The `HTTPBearer(auto_error=False)` setting means missing tokens don't automatically reject the request — the endpoint handler decides what to do.

---

## 13. Middleware

### RequestLoggingMiddleware

Added to the app stack, it logs every HTTP request:

```python
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start_time) * 1000

        if request.url.path != "/health":  # Skip health checks
            logger.info("http_request",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 1),
            )
        return response
```

**Output example** (development):
```
14:32:01 [info] http_request
    method: GET
    path: /api/v1/questions
    status_code: 200
    duration_ms: 45.3
```

**Output example** (production, JSON):
```json
{"event": "http_request", "method": "GET", "path": "/api/v1/questions", "status_code": 200, "duration_ms": 45.3, "timestamp": "2026-04-07T14:32:01Z"}
```

---

## 14. Error Handling

### Global Exception Handler

Catches any unhandled exception and returns a clean error:

```python
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception",
        method=request.method,
        path=request.url.path,
        error_type=type(exc).__name__,
        error_message=str(exc),
        traceback=traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again later."},
    )
```

**What this does:**
- Logs the full traceback server-side (for developers)
- Returns a generic message to the client (no stack traces leaked)
- Prevents the server from crashing on unexpected errors

### Endpoint-Level Errors

Individual endpoints raise `HTTPException` for expected errors:

```python
if not user:
    raise HTTPException(status_code=401, detail="Invalid username or password")

if question is None:
    raise HTTPException(status_code=404, detail="Question not found")
```

FastAPI automatically converts these to JSON responses: `{"detail": "..."}`.

---

## 15. Logging

### structlog Configuration

The logging system is configured differently for dev and prod:

**Development** — Pretty colored console output:
```python
processors = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="%H:%M:%S"),
    structlog.dev.ConsoleRenderer(colors=True),
]
```

**Production** — JSON output (for log aggregation tools like ELK, Loki, etc.):
```python
processors = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.JSONRenderer(),
]
```

**How to use:**
```python
import structlog
logger = structlog.get_logger()

logger.info("User logged in", user_id="abc123", ip="1.2.3.4")
logger.error("RAG failed", question_id="xyz", error="timeout")
```

**Structured vs unstructured**: Unlike `print()` or `logging.info("...")`, structlog attaches **key-value pairs** to every log entry. This means you can search logs programmatically: `grep '"question_id":"abc123"'` or use a log aggregator to query by field.

---

## 16. Rate Limiting

### SlowAPI Configuration

```python
limiter = Limiter(key_func=get_remote_address)  # Per-IP rate limiting
```

**Currently limited:**
- `GET /health` → 10 requests/minute

**Not limited** (potential improvement):
- `/auth/register` and `/auth/login` — vulnerable to brute-force
- All other endpoints

**How it works**: SlowAPI tracks request counts in memory per IP address. If an IP exceeds the limit, it returns `429 Too Many Requests`. The counter resets when the server restarts (in-memory storage).

---

## 17. What Is RAG?

### The Problem RAG Solves

Large Language Models (LLMs) like GPT, Qwen, etc. are trained on general internet data. They don't know about **your specific course materials**. If you ask "How do I use `append()` in the lab?", a generic LLM will give a general Python answer — which might not match what your lab teaches.

**RAG (Retrieval-Augmented Generation)** solves this by:
1. **Retrieving** relevant documents from your knowledge base
2. **Augmenting** the LLM's prompt with those documents as context
3. **Generating** an answer based on both the context and the LLM's general knowledge

### The RAG Pipeline, Explained Simply

Think of it like this: you have a very smart teaching assistant (the LLM), but they haven't read your lab manual. RAG works by:

1. You ask a question
2. The system finds the most relevant pages from the lab manual
3. It gives those pages to the TA along with your question
4. The TA reads the manual pages and answers your question based on them

This means the AI's answer is **grounded in your actual course materials**, not just general knowledge.

### Why Not Just Fine-Tune the Model?

Fine-tuning requires expensive GPU time and produces a model that can't easily be updated when course materials change. RAG works with any LLM, updates instantly when you add new documents, and is much cheaper to run.

---

## 18. How LabAssist Uses RAG

The RAG pipeline is triggered **every time a student posts a new question**. Here's the complete flow:

```
Student posts question
        ↓
[1] EMBED: Convert question text → 384-dimensional vector
        ↓
[2] RETRIEVE: Search lab_doc table for most similar chunks
        ↓
[3] FILTER: If no strong matches, discard context
        ↓
[4] PROMPT: Build conversation messages with system prompt + context
        ↓
[5] CALL LLM: Send to Qwen API, get answer back
        ↓
[6] PARSE: Extract answer text and confidence score
        ↓
[7] STORE: Create Answer record, update Question status
```

**Key constants:**
- `SIMILARITY_THRESHOLD = 0.25` — minimum cosine similarity for a chunk
- `STRONG_MATCH_THRESHOLD = 0.35` — above this, chunks are likely relevant
- `MAX_DOCS = 20` — maximum chunks to retrieve
- `MAX_CONTEXT_CHARS = 120,000` — maximum total context size (~25K tokens)
- `LLM_TIMEOUT = 120.0` seconds

---

## 19. Embedding System

### What Are Embeddings?

An **embedding** is a way to represent text as a list of numbers (a vector). The key property: **similar texts have similar vectors**. "How do lists work?" and "How to use append()" will have closer vectors than "How do lists work?" and "What is Git?".

### Model Used

```
Model: sentence-transformers/all-MiniLM-L6-v2
Dimensions: 384
Size: ~80 MB
Runtime: CPU (no GPU needed)
```

This model was chosen because:
- It's **small** (80 MB) — downloads and loads quickly
- It runs on **CPU** — no expensive GPU needed
- It's **good enough** for short text (questions and lab docs)
- It's **free and open-source**

### EmbeddingService

```python
class EmbeddingService:
    """Singleton — only one model in memory."""
    _instance = None
    _model = None

    def _load_model(self):
        """Lazy loading — model isn't loaded until first use."""
        if self._model is None:
            self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    def embed(self, text: str) -> List[float]:
        self._load_model()
        return self._model.encode(text).tolist()
```

**Why lazy loading?** The model takes ~5 seconds to load and uses ~500 MB RAM. By loading it only when first needed, the server starts faster and doesn't waste memory if no questions are asked.

**Why singleton?** Loading the model once is enough. After that, it stays in memory and can encode any number of texts.

### How to Embed Text

```python
from app.services.embeddings import embed_text

vector = embed_text("How do I use append() with lists?")
# Returns: [0.023, -0.145, 0.089, ..., 0.012]  (384 numbers)
```

---

## 20. Document Chunking

### Why Chunk?

LLMs have a **context window** — a maximum number of tokens they can process. If you shove an entire 50-page lab manual into the prompt, it will exceed the limit. Also, the AI answer quality depends on **relevant context** — including unrelated sections adds noise.

**Solution**: Split lab documents into smaller chunks. Each chunk is embedded separately so semantic search retrieves only the relevant pieces.

### Chunking Strategy

```python
def chunk_lab_content(content: str, title: str = "") -> list[str]:
    # Step 1: If content is small enough, keep as single chunk
    if len(content) <= 15_000:
        return [content]

    # Step 2: Split on ## heading boundaries (natural section breaks)
    sections = re.split(r'(\n## )', content)

    # Step 3: Reassemble sections, hard-splitting any that exceed 15K chars
    # Hard split tries to break at paragraph boundaries (\n\n)
```

**Chunk size**: 15,000 characters ≈ 3,750 tokens. With a 120,000-char context budget, this allows ~8 chunks in the prompt.

**Why split at `##` headings?** Markdown `##` headings typically mark new sections or exercises. Splitting here keeps related content together and separates unrelated topics.

### Example

A lab document with:
```
# Lab 3: File I/O

## Reading Files
[2,000 chars of content]

## Writing Files
[3,000 chars of content]

## Error Handling
[8,000 chars of content]
```

Total: ~13,000 chars → stays as one chunk (under 15K limit).

A larger lab with 40,000 chars → split into 3-4 chunks at `##` boundaries.

---

## 21. Vector Search (pgvector)

### What Is pgvector?

**pgvector** is a PostgreSQL extension that adds vector data types and similarity search. It allows you to:
1. Store embedding vectors in a column (`VECTOR(384)`)
2. Query by similarity using distance operators

Without pgvector, you'd need a separate vector database (like Pinecone or Milvus). With pgvector, everything stays in one database.

### Distance Metric: Cosine Similarity

The query uses **cosine distance** (`<=>`):
```sql
1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
```

- `<=>` returns the cosine distance (0 = identical, 2 = opposite)
- `1 - distance` gives cosine similarity (1 = identical, 0 = unrelated, -1 = opposite)
- Results are ordered by similarity (most similar first)

### Why Cosine Similarity?

Cosine similarity measures the **angle** between two vectors, not their magnitude. This means:
- Two texts about the same topic will have a small angle (high similarity) regardless of length
- It's the standard metric for text embeddings

---

## 22. Retrieval Logic

The retrieval step (`retrieve_context` in `rag.py`) is smarter than a simple vector search:

### Lab Number Filtering

If the question text mentions specific lab numbers, the search is filtered:

```python
def extract_lab_numbers(question_text: str) -> list[int]:
    # Regex: matches "lab 4", "Lab #5", "LAB 3", etc.
    return sorted(set(int(m) for m in re.findall(r'\blab\s*#?(\d+)\b', question_text, re.IGNORECASE)))
```

**Example**: If the question says "In lab 3, I can't read the file", the regex extracts `[3]` and the SQL query adds `WHERE lab_number IN (3)`.

**Why this matters**: Without filtering, a question about "Lab 1: Python basics" might retrieve chunks from "Lab 5: Git" if they happen to have similar vocabulary. With filtering, you get only Lab 1 content.

### Threshold Behavior

| Scenario | Behavior |
|----------|----------|
| Lab number mentioned | Accept ALL chunks from those labs (no similarity threshold) |
| No lab mentioned, strong match (≥0.35) | Include chunk |
| No lab mentioned, weak match (<0.35) | Discard chunk |
| No chunks pass threshold | Set context to empty → LLM answers from general knowledge |

### Max Results

```python
top_k = 20  # Maximum chunks to retrieve
```

Even if 100 chunks match, only the top 20 most similar ones are used.

---

## 23. Prompt Engineering

### System Prompt

The system prompt instructs the LLM how to behave:

```
You are a helpful teaching assistant for a programming lab course.
Answer student questions based on the provided lab materials when possible.

Rules:
- If the context contains relevant information, use it to form your answer and cite the lab number(s).
- When multiple labs are referenced, synthesize across them — explain how concepts evolve from lab to lab.
- If the context is NOT relevant or doesn't help, answer from your general programming knowledge.
  Clearly state "This is not covered in the lab materials, but here's what I know:" before your answer.
- Always end your response with a confidence score between 0.0 and 1.0.
- Keep answers clear, practical, and example-driven.

Format your response like this:
ANSWER: <your detailed answer>
CONFIDENCE: <0.0 to 1.0>
```

**Why this format?** The `ANSWER:` and `CONFIDENCE:` markers make it easy to parse the response with regex. The system prompt ensures consistent behavior.

### User Prompt

```
Question: {title}

{body}

---

Relevant lab materials:

### Lab 3 (part 1/2): File I/O
{chunk content}

---

### Lab 3 (part 2/2): File I/O
{chunk content}
```

**Context formatting rules:**
- Chunks are grouped by lab number
- Each chunk is labeled with its part number (`part X/Y`)
- Chunks are separated by `---`
- Total context capped at 120,000 characters

---

## 24. LLM Integration

### API Call

The LLM is called via HTTP POST to an OpenAI-compatible endpoint:

```python
async def call_llm(messages: List[dict]) -> str:
    payload = {
        "model": "coder-model",       # Model name in qwen-code-api
        "messages": messages,          # System + user messages
        "temperature": 0.3,            # Low = more deterministic
        "max_tokens": 1024,            # Max response length
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.llm_api_base}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json=payload,
        )
        return response.json()["choices"][0]["message"]["content"]
```

### Parameters Explained

| Parameter | Value | Why |
|-----------|-------|-----|
| `model` | `coder-model` | The model name registered in qwen-code-api |
| `temperature` | `0.3` | Low temperature = consistent, focused answers. Higher (0.7-1.0) would make it more creative but less reliable |
| `max_tokens` | `1024` | Limits response length. ~1024 tokens ≈ 750 words |
| `timeout` | `120s` | Network timeout. If the LLM takes longer, the request fails |

### Error Handling

| Error | Response to User |
|-------|-----------------|
| Timeout | "⚠️ The AI service timed out. A TA will review your question." |
| HTTP error (e.g., 500) | "⚠️ The AI service returned an error (500). A TA will review your question." |
| Other exception | "⚠️ The AI service encountered an unexpected error (ErrorType). A TA will review your question." |

In all error cases, the question status is set to `open` so it appears in the TA queue.

---

## 25. Response Parsing

The LLM is expected to respond in this format:
```
ANSWER: To use append() with lists in Python, call the method on a list object...

CONFIDENCE: 0.85
```

The parser extracts these with regex:

```python
def parse_llm_response(response_text: str) -> Tuple[str, float]:
    # Extract confidence
    confidence_match = re.search(r"CONFIDENCE:\s*([0.9.]+)", response_text, re.IGNORECASE)
    confidence = float(confidence_match.group(1)) if confidence_match else 0.5

    # Remove CONFIDENCE line
    answer_text = re.sub(r"\n?\s*CONFIDENCE:\s*[0-9.]+\s*$", "", response_text, flags=re.IGNORECASE).strip()

    # Remove ANSWER: prefix
    answer_text = re.sub(r"^ANSWER:\s*", "", answer_text, flags=re.IGNORECASE).strip()

    return answer_text, confidence
```

**Fallback**: If the LLM doesn't include a confidence score, it defaults to 0.5. If it doesn't follow the format at all, the entire response becomes the answer text.

---

## 26. Background Task Processing

### How It Works

When a question is created, the AI answer is generated **asynchronously** using FastAPI's `BackgroundTasks`:

```python
@router.post("/questions")
async def create_question(data: QuestionCreate, background_tasks: BackgroundTasks, ...):
    question = Question(title=data.title, body=data.body, status="analyzing")
    session.add(question)
    await session.commit()

    # Schedule background task — runs AFTER the response is sent
    background_tasks.add_task(_generate_ai_answer, str(question.id), data.title, data.body)

    return question  # Sent to client immediately
```

### The Background Task

```python
async def _generate_ai_answer(question_id_str: str, title: str, body: str):
    # Creates its OWN database engine (can't reuse the request's session)
    engine = create_async_engine(settings.database_url)
    AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        # Run RAG pipeline
        answer_text, confidence, lab_numbers = await run_rag_pipeline(title, body, session)

        # Create answer and update question
        # ...

    await engine.dispose()  # Clean up connections
```

**Why its own engine?** The background task runs after the HTTP request's database session is closed. It needs its own connection pool.

### Timing Measurement

```python
start_time = time.time()
answer_text, confidence, lab_numbers = await run_rag_pipeline(...)
reasoning_time = round(time.time() - start_time, 2)
```

This measures the **wall-clock time** from starting the RAG pipeline to getting the answer back. It includes embedding, vector search, API call, and parsing.

---

## 27. What Is qwen-code-api?

### Overview

`qwen-code-api/` is a **vendored project** (included in this repository) that acts as a proxy between LabAssist and the Qwen Code AI service. It exposes an **OpenAI-compatible API** (`/v1/chat/completions`) while handling OAuth authentication with Qwen behind the scenes.

### Why It Exists

Qwen Code doesn't provide a standard API key. Instead, it uses OAuth authentication through a CLI tool. The qwen-code-api proxy:
1. Handles the OAuth flow (browser redirect → token exchange)
2. Translates OpenAI-format requests to Qwen's internal format
3. Exposes a standard `/v1/chat/completions` endpoint that LabAssist can call

### Is It Required?

**No, not strictly.** You can use **any** OpenAI-compatible API endpoint:

| LLM Backend | `LLM_API_BASE` | Requires qwen-code-api? |
|-------------|---------------|------------------------|
| Qwen Code (free via OAuth) | `http://<host>:8080/v1` | ✅ Yes — this is what qwen-code-api provides |
| DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` | ❌ No |
| Ollama (local) | `http://<host>:11434/v1` | ❌ No |
| vLLM | `http://<host>:8000/v1` | ❌ No |
| llama.cpp server | `http://<host>:8080/v1` | ❌ No |
| OpenAI | `https://api.openai.com/v1` | ❌ No |

**If you use Qwen Code via OAuth for free**, qwen-code-api is the bridge that makes it work. If you use any other provider, just point `LLM_API_BASE` there and skip qwen-code-api entirely.

### Important: It's a Separate Docker Compose Project

qwen-code-api has its **own** `docker-compose.yml` and runs **independently** from LabAssist. LabAssist does **not** start it automatically. You must start it yourself before LabAssist can use it.

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  LabAssist      │     │  qwen-code-api   │     │  Qwen Code      │
│  docker-compose │────►│  docker-compose  │────►│  (external API) │
│  (main stack)   │     │  (separate)      │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

### Architecture

```
┌─────────────────────────────────────────┐
│         qwen-code-api container         │
│                                         │
│  Port 8080 (configurable via HOST_PORT) │
│                                         │
│  /v1/chat/completions  ← OpenAI format  │
│  /v1/models            ← model listing   │
│  /health               ← health check    │
│                                         │
│  ┌───────────────────┐                  │
│  │ OAuth handler     │ → credentials at │
│  │ (manages tokens)  │   /mnt/qwen-creds│
│  └───────────────────┘                  │
│                                         │
│  ┌───────────────────┐                  │
│  │ Request/Response  │ ← Translates     │
│  │ translator        │   OpenAI ↔ Qwen  │
│  └───────────────────┘                  │
└─────────────────────────────────────────┘
```

### How to Set It Up (First Time)

```bash
cd /root/LabAssist/qwen-code-api
cp .env.example .env
```

Edit `.env`:
```env
# Authentication — use your Qwen OAuth credentials
QWEN_CODE_AUTH_USE=true
QWEN_CODE_API_KEY=your-qwen-api-key

# Server configuration
PORT=8080
ADDRESS=0.0.0.0
LOG_LEVEL=error
DEFAULT_MODEL=coder-model

# Network (where LabAssist will connect from)
HOST_ADDRESS=127.0.0.1
HOST_PORT=8080
```

Start it:
```bash
cd /root/LabAssist/qwen-code-api
docker compose up -d --build
```

### How to Verify It's Running

```bash
# Check container status
docker compose ps

# Test health endpoint
curl http://localhost:8080/health

# Test model listing
curl http://localhost:8080/v1/models

# Test a chat completion
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "coder-model",
    "messages": [{"role": "user", "content": "Say hello"}],
    "max_tokens": 50
  }'
```

### Container Name and Networking

The container is named `qwen-code-api-qwen-code-api-1` by Docker Compose (format: `<project>-<service>-1`). This matters because:

**LabAssist needs to connect to this container.** The URL depends on your network setup:

| Setup | `LLM_API_BASE` value |
|-------|---------------------|
| LabAssist on same host, qwen-code-api on host port | `http://host.docker.internal:8080/v1` |
| LabAssist on same host (Linux) | `http://172.17.0.1:8080/v1` (Docker bridge IP) |
| LabAssist on same host, port bound to 0.0.0.0 | `http://<host-ip>:8080/v1` |
| Both in shared Docker network | `http://qwen-code-api:8080/v1` |

**In your LabAssist `.env`:**
```env
# If qwen-code-api runs on the same host
LLM_API_BASE=http://host.docker.internal:8080/v1
# On Linux, use your host IP instead:
# LLM_API_BASE=http://172.17.0.1:8080/v1
```

### Managing the Container

| Action | Command |
|--------|---------|
| **Start** | `cd qwen-code-api && docker compose up -d --build` |
| **Stop** | `cd qwen-code-api && docker compose down` |
| **Restart** | `cd qwen-code-api && docker compose restart` |
| **View logs** | `cd qwen-code-api && docker compose logs -f` |
| **View logs (last 50 lines)** | `cd qwen-code-api && docker compose logs --tail=50` |
| **Stop + remove containers** | `cd qwen-code-api && docker compose down --remove-orphans` |
| **Stop + remove + delete data** | `cd qwen-code-api && docker compose down -v --remove-orphans` |
| **Rebuild after code changes** | `cd qwen-code-api && docker compose up -d --build --no-deps` |
| **Check status** | `cd qwen-code-api && docker compose ps` |

### OAuth Token Management

Qwen OAuth tokens expire (typically every 30-90 days). When they expire, the proxy will fail to authenticate with Qwen, and LabAssist will get errors from the LLM API.

#### Token Expiry Check Script

`scripts/check-qwen-oauth-expiry.sh` checks the token expiry date and prints a warning if it's expiring soon (within 7 days):

```bash
#!/bin/bash
# Usage: run manually or via cron
bash /root/LabAssist/scripts/check-qwen-oauth-expiry.sh
```

**How it works:**
1. Reads the OAuth credentials file at `/root/.qwen/oauth_creds.json`
2. Extracts the expiry timestamp
3. Compares against current time
4. Prints a colored warning if expiring within 7 days

#### Token Refresh Script

`scripts/refresh-qwen-oauth.sh` re-authenticates with Qwen and restarts the proxy:

```bash
bash /root/LabAssist/scripts/refresh-qwen-oauth.sh
```

**How it works:**
1. Runs `qwen auth qwen-oauth` to re-authenticate (may require browser interaction)
2. Stops the qwen-code-api container
3. Starts it again so it picks up the new credentials
4. Reconnects to the Docker network
5. Verifies the health endpoint

#### Setting Up Automatic Monitoring

Add to your crontab (`crontab -e`):

```bash
# Check token expiry daily at 9 AM
0 9 * * * bash /root/LabAssist/scripts/check-qwen-oauth-expiry.sh >> /var/log/qwen-oauth-check.log 2>&1
```

**Important limitation:** The refresh script likely requires interactive OAuth (browser redirect), so it **cannot** run unattended in cron. You'll need to manually run it when the token expires. If you need fully automatic token management, consider switching to DashScope (which uses a static API key) or another provider.

### Updating qwen-code-api

```bash
# 1. Pull latest code
cd /root/LabAssist/qwen-code-api
git pull

# 2. Rebuild and restart
docker compose up -d --build

# 3. Verify
curl http://localhost:8080/health
```

### Troubleshooting

#### Proxy Won't Start

```bash
# Check logs
cd qwen-code-api && docker compose logs

# Common causes:
# 1. Port 8080 already in use — change HOST_PORT in .env
# 2. Invalid OAuth credentials — check QWEN_CODE_API_KEY in .env
# 3. Missing credentials file — ensure /root/.qwen/oauth_creds.json exists
```

#### LabAssist Can't Connect

```bash
# Test connectivity from the host
curl http://localhost:8080/health

# If that works but LabAssist can't connect, it's a Docker networking issue.
# Test from inside the LabAssist backend container:
docker compose exec backend python -c "
import httpx
r = httpx.get('http://host.docker.internal:8080/health')
print(r.status_code)
"
# On Linux, replace host.docker.internal with your host IP (ip addr show docker0)
```

#### OAuth Token Expired

**Symptoms:** LLM API calls return 401 errors, LabAssist shows "AI service returned an error."

```bash
# Check token status
cat /root/.qwen/oauth_creds.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('expires_at', 'unknown'))"

# Re-authenticate
cd /root/LabAssist/qwen-code-api
qwen auth qwen-oauth   # Follow browser redirect
docker compose restart
```

#### Model Not Found (coder-model)

```bash
# Check available models
curl http://localhost:8080/v1/models | python3 -m json.tool

# If coder-model isn't listed, the proxy may be misconfigured.
# The default model is set via DEFAULT_MODEL=coder-model in qwen-code-api .env
```

---

## 28. How RAG Connects with qwen-code-api

Here's the complete connection flow:

```
LabAssist backend (rag.py)
    ↓
call_llm() sends POST to settings.llm_api_base/chat/completions
    ↓
Example: POST http://host.docker.internal:8080/v1/chat/completions
    ↓
qwen-code-api proxy receives the request
    ↓
Proxy translates OpenAI format → Qwen internal format
    ↓
Proxy calls Qwen API (with OAuth token)
    ↓
Qwen generates response
    ↓
Proxy translates response → OpenAI format
    ↓
LabAssist backend receives and parses response
```

**Configuration**:
```env
# In LabAssist .env
LLM_API_BASE=http://host.docker.internal:8080/v1
LLM_API_KEY=your-api-key

# The model name is hardcoded as "coder-model" in rag.py
```

The `LLM_API_KEY` may be empty if the proxy doesn't require additional authentication — the proxy handles OAuth internally.

**Note**: If you use a different LLM provider (Ollama, DashScope, etc.), the flow is the same but skips the qwen-code-api proxy step. LabAssist calls the LLM endpoint directly.

---

## 29. Database Schema

### Complete Schema with All Columns

#### `user` Table
```
Column          | Type          | Constraints
----------------|---------------|-----------------------------------
id              | UUID          | PK, default uuid4()
username        | VARCHAR(50)   | UNIQUE, INDEXED, NOT NULL
password_hash   | VARCHAR(255)  | NOT NULL (bcrypt hash)
role            | VARCHAR       | DEFAULT 'student' (student/ta/admin)
created_at      | TIMESTAMP     | DEFAULT now()
```

**Relationships**: A user has many questions, answers, and ratings.

#### `question` Table
```
Column                    | Type          | Constraints
--------------------------|---------------|-----------------------------------
id                        | UUID          | PK, default uuid4()
user_id                   | UUID          | FK → user.id
title                     | VARCHAR(200)  | NOT NULL
body                      | TEXT          | NOT NULL
status                    | VARCHAR       | DEFAULT 'analyzing' (analyzing/open/answered/needs_review)
ai_answer_id              | UUID          | FK → answer.id, NULLABLE
hidden                    | BOOLEAN       | DEFAULT FALSE
ai_reasoning_time_seconds | FLOAT         | NULLABLE
embedding                 | VECTOR(384)   | NULLABLE (pgvector, for semantic search)
created_at                | TIMESTAMP     | DEFAULT now()
updated_at                | TIMESTAMP     | DEFAULT now()
```

**Relationships**: A question belongs to a user and has many answers.

#### `answer` Table
```
Column                 | Type        | Constraints
-----------------------|-------------|-----------------------------------
id                     | UUID        | PK, default uuid4()
question_id            | UUID        | FK → question.id
user_id                | UUID        | FK → user.id, NULLABLE (NULL for AI)
body                   | TEXT        | NOT NULL
source                 | VARCHAR     | NOT NULL (ai/ta/student)
confidence             | FLOAT       | 0.0-1.0, NULLABLE
edited                 | BOOLEAN     | DEFAULT FALSE
reasoning_time_seconds | FLOAT       | NULLABLE
created_at             | TIMESTAMP   | DEFAULT now()
```

**Relationships**: An answer belongs to a question and optionally a user. It has many ratings.

#### `rating` Table
```
Column      | Type      | Constraints
------------|-----------|-----------------------------------
id          | UUID      | PK, default uuid4()
answer_id   | UUID      | FK → answer.id
user_id     | UUID      | FK → user.id
helpful     | BOOLEAN   | NOT NULL
created_at  | TIMESTAMP | DEFAULT now()
```

**Relationships**: A rating belongss to an answer and a user.

#### `lab_doc` Table
```
Column        | Type        | Constraints
--------------|-------------|-----------------------------------
id            | UUID        | PK, default uuid4()
lab_number    | INTEGER     | NOT NULL
title         | VARCHAR     | NOT NULL
content       | TEXT        | NOT NULL
embedding     | VECTOR(384) | NULLABLE (pgvector)
chunk_index   | INTEGER     | DEFAULT 0 (position within original doc)
num_chunks    | INTEGER     | DEFAULT 1 (total chunks doc was split into)
updated_at    | TIMESTAMP   | DEFAULT now()
```

**No relationships**: Lab docs are standalone reference materials.

### Entity Relationship Diagram

```
user (1) ────────< question (N)
                      │
                      ├────< answer (N) ────< rating (N)
                      │                          │
                      └── ai_answer_id ──────────┘

user (1) ────────< answer (N)
user (1) ────────< rating (N)

lab_doc (standalone reference data)
```

---

## 30. Migrations (Alembic)

### What Are Migrations?

Migrations are version control for your database schema. When you add a column, create a migration file. When someone else runs the app, they apply all pending migrations to get the same schema.

### Alembic Setup

Alembic is configured in `backend/alembic.ini` and `backend/alembic/env.py`.

**Key configuration in `env.py`:**
```python
from app.models.models import User, Question, Answer, Rating, LabDoc  # Import all models
target_metadata = SQLModel.metadata  # Alembic reads model definitions

def run_migrations_online():
    # Override the URL from settings (not from alembic.ini)
    connectable = create_engine(settings.sync_database_url, poolclass=pool.NullPool)
```

### Migration History

| Migration File | What It Does |
|----------------|-------------|
| `4a95a59a5d41` | Initial: creates user, question, answer, rating, lab_doc tables |
| `b7c3e1a9f2d4` | Adds pgvector extension + embedding column to lab_doc |
| `d8e4f2b1c3a5` | Adds embedding column to question table |
| `e9f5a3b2d4c6` | Adds `edited` boolean to answer |
| `f1a2b3c4d5e6` | Adds `hidden` boolean to question |
| `a2b3c4d5e6f7` | Adds `reasoning_time_seconds` to answer |
| `b3c4d5e6f7a8` | Adds `ai_reasoning_time_seconds` to question |
| `a1b2c3d4e5f7` | Adds `chunk_index` and `num_chunks` to lab_doc |

### Running Migrations

```bash
# Inside the backend container
alembic upgrade head     # Apply all pending migrations

# Or via Docker Compose
docker compose exec backend alembic upgrade head
```

### Creating a New Migration

```bash
# After modifying models/models.py
alembic revision --autogenerate -m "add new_column to table"

# This creates a migration file in alembic/versions/
# Review the file before committing!
```

---

## 31. Seeding

### What Is Seeding?

Seeding populates the database with initial data — demo users and lab documents.

### Seed Script (`python -m seed`)

Located in `backend/seed/__main__.py`. It:

1. Creates an admin user: `admin` / `admin123`
2. Reads all `.md` files from the `seed/` directory
3. Extracts title and lab number from filenames
4. Chunks each file using `chunk_lab_content()`
5. Creates a `LabDoc` record for each chunk

```bash
# Run seeding
docker compose exec backend python -m seed

# Output:
# Seeding database...
#   Created 1 user: admin
#   Created 5 lab document chunk(s):
#     - Lab 1: Intro to Python (1 chunk)
#     - Lab 2: Data Structures (2 chunks)
#     - Lab 3: File I/O (2 chunks)
# Seeding complete!
```

**Note**: The seed script does **not** generate embeddings. Embeddings are generated when the RAG pipeline runs or when you run `python -m embed_docs`.

### GitHub Ingestion Script (`python -m seed.ingest_github`)

Located in `backend/seed/ingest_github.py`. It:

1. Clones a GitHub repository to a temporary directory
2. Finds all `.md` files (skipping LICENSE, CHANGELOG, etc.)
3. Concatenates them into one document
4. Determines lab number and title (from args, repo name, or first heading)
5. Chunks the content
6. Generates embeddings (using EmbeddingService)
7. Inserts LabDoc records with embeddings

```bash
docker compose exec backend python -m seed.ingest_github https://github.com/user/lab-materials --lab-number 4
```

**Overwrite behavior**: If the lab number already exists, it prompts "Overwrite? (y/N):". In non-interactive environments (Docker), this will hang — future improvement: add a `--overwrite` flag.

---

## 32. Vector Embeddings in PostgreSQL

### How pgvector Works in LabAssist

1. **Extension activation**: The `b7c3e1a9f2d4` migration runs `CREATE EXTENSION IF NOT EXISTS vector;`
2. **Column type**: `embedding = Column(Vector(384))` creates a column that stores 384-dimensional vectors
3. **Query format**: Vectors are passed as strings: `"[0.023, -0.145, ...]"`
4. **Distance operator**: `<=>` computes cosine distance between two vectors

### Example Query

```python
embedding_str = str(question_embedding)  # "[0.023, -0.145, ...]"
query = text("""
    SELECT id, lab_number, title, content,
           1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
    FROM lab_doc
    ORDER BY embedding <=> CAST(:embedding AS vector)
    LIMIT 20
""")
result = await session.execute(query, {"embedding": embedding_str})
```

### Why Store Embeddings as Strings?

SQLAlchemy's text queries expect scalar parameters. The pgvector extension accepts a string representation of a list (`"[0.1, 0.2, ...]"`) and casts it to a vector internally.

---

## 33. Frontend Architecture

### Technology Choices

| Technology | Purpose | Why |
|------------|---------|-----|
| React 18 | UI framework | Component-based, huge ecosystem |
| TypeScript | Type safety | Catches bugs at compile time, great IDE support |
| Vite 5 | Build tool + dev server | Fast hot-reload, modern |
| React Router v6 | Client-side routing | Declarative, nested routes |
| Axios | HTTP client | Request/response interceptors, easy API |
| react-markdown | Markdown rendering | Renders AI answers with formatting |

### Project Structure

```
frontend/src/
├── api/
│   └── client.ts           # Axios instance + typed API methods
├── context/
│   └── AuthContext.tsx     # Auth state (user, token, login, logout)
├── components/
│   ├── Navbar.tsx          # Top navigation
│   ├── QuestionCard.tsx    # Question summary card
│   └── AnswerCard.tsx      # Full answer with rating/editing
├── pages/
│   ├── Login.tsx
│   ├── Register.tsx
│   ├── QuestionsList.tsx
│   ├── QuestionDetail.tsx
│   ├── AskQuestion.tsx
│   ├── TAQueue.tsx
│   └── Stats.tsx
├── types/
│   └── index.ts            # TypeScript interfaces
├── styles/
│   └── global.css          # Global CSS
├── App.tsx                 # Router + protected routes
└── main.tsx                # React entry point
```

---

## 34. Page Components

### QuestionsListPage (`/`)

The homepage. Shows a filterable list of all questions.

**Features:**
- Status filter buttons: All, 🤖 Analyzing, 🔍 Open, ✅ Answered
- "Ask Question" button (only if authenticated)
- Each question rendered as a QuestionCard
- Loads questions from `GET /api/v1/questions`

### QuestionDetailPage (`/questions/:id`)

Shows a single question with all its answers.

**Features:**
- Full question text
- Status indicator
- Answers rendered as AnswerCards
- **AI polling**: If no AI answer yet, polls every 2 seconds
- TA answer form (only visible to TA+ users)
- "Back to questions" button

### AskQuestionPage (`/questions/new`)

Form to create a new question.

**Features:**
- Title input (max 200 chars, with char counter)
- Details textarea
- **Live duplicate detection**: As you type (debounced 500ms), searches for similar questions and shows them with similarity percentages
- Suggested questions are clickable links
- On submit, navigates to the new question's detail page

### LoginPage (`/login`)

Standard login form. On success, stores token in localStorage and navigates to `/`.

### RegisterPage (`/register`)

Registration form with password confirmation. On success, auto-logs in and navigates to `/`.

### TAQueuePage (`/ta/queue`)

The TA review queue. Only accessible to TA+ users.

**Features:**
- Shows AI answers that need review (👎 rated or low confidence)
- Displays thumbs up/down counts and AI confidence
- Reply form for each flagged answer
- Admin-only: hide/unhide buttons
- Auto-refreshes every 3 seconds
- Questions with a TA answer that has ≥1 👍 are automatically removed

### StatsPage (`/stats`)

Forum analytics dashboard.

**Shows:**
- Total questions, users, TAs, lab documents
- Question status breakdown
- AI performance: answer count, avg confidence, high/low confidence counts, reasoning time (min/max/avg)
- Rating quality: helpful vs not helpful bar chart
- Top 5 most active users

---

## 35. Shared Components

### Navbar

Top navigation bar with role-aware links:
- Unauthenticated: "Login" + "Register"
- Authenticated: "Stats" + username/role + "Logout"
- TA+: "🔍 TA Queue" link appears

### QuestionCard

Summary card in the list view:
- Title (clickable link to detail page)
- Status badge (color-coded: orange=analyzing, red=open, green=answered)
- Body preview (first 120 chars)
- Date
- AI reasoning time badge (if available)

### AnswerCard

Full answer display:
- Source badge: 🤖 AI, 👨‍🏫 TA, or 🎓 Student
- Confidence percentage (with ⚠️ if <50%)
- AI reasoning time
- Markdown-rendered body (via react-markdown)
- Rating stats (👍 count, 👎 count)
- 👍/👎 buttons
- User's own vote indicator
- Edit/delete buttons (for TA own or Admin any non-AI)
- Inline editing form
- Inline delete confirmation

---

## 36. State Management

### AuthContext

Uses React Context + localStorage for persistence:

```typescript
interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (username, password) => Promise<void>;
  register: (username, password) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  isTA: boolean;
}
```

**How it works:**
1. On mount, reads `user` and `token` from localStorage
2. `login()` calls the API, decodes JWT payload, stores in state + localStorage
3. `logout()` clears state + localStorage
4. `isAuthenticated` = token !== null && user !== null
5. `isTA` = user role is "ta" or "admin"

**JWT decoding** (frontend):
```typescript
const payload = JSON.parse(atob(newToken.split(".")[1]));
const userData = {
  id: payload.sub,        // User ID from JWT
  username,               // From login form (not from JWT)
  role: payload.role,     // From JWT
  created_at: new Date().toISOString(),  // Fake (not from JWT)
};
```

**Note**: The `created_at` field is faked on login because the JWT doesn't contain it. The actual `created_at` lives in the database.

---

## 37. API Client

### Axios Instance

```typescript
const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});
```

### JWT Interceptor

```typescript
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

**Every request** automatically gets the JWT token if it exists. No need to manually attach it.

### Typed API Methods

```typescript
export const authApi = {
  login: (username, password) => api.post("/auth/login", { username, password }),
  register: (username, password, role = "student") =>
    api.post("/auth/register", { username, password, role }),
};

export const questionsApi = {
  list: (status?: string) => api.get("/questions", { params: status ? { status } : {} }),
  get: (id: string) => api.get(`/questions/${id}`),
  create: (title: string, body: string) => api.post("/questions", { title, body }),
};

export const answersApi = {
  add: (questionId: string, bodyText: string) =>
    api.post(`/questions/${questionId}/answer`, { body: bodyText }),
  rate: (answerId: string, helpful: boolean) =>
    api.post(`/answers/${answerId}/rate`, { helpful }),
};

export const taApi = {
  flagged: () => api.get("/ta/flagged"),
  addAnswer: (questionId: string, bodyText: string) =>
    api.post(`/ta/questions/${questionId}/answer`, { body: bodyText }),
  editAnswer: (answerId: string, bodyText: string) =>
    api.put(`/answers/${answerId}`, { body: bodyText }),
  deleteAnswer: (answerId: string) => api.delete(`/answers/${answerId}`),
  hideQuestion: (questionId: string) =>
    api.put(`/questions/${questionId}/hide`),
  unhideQuestion: (questionId: string) =>
    api.put(`/questions/${questionId}/unhide`),
};
```

---

## 38. Routing

### Route Definitions

```typescript
<Routes>
  <Route path="/" element={<QuestionsListPage />} />
  <Route path="/login" element={<LoginPage />} />
  <Route path="/register" element={<RegisterPage />} />
  <Route path="/questions/new" element={
    <ProtectedRoute><AskQuestionPage /></ProtectedRoute>
  } />
  <Route path="/ta/queue" element={
    <ProtectedRoute><TAQueuePage /></ProtectedRoute>
  } />
  <Route path="/questions/:id" element={<QuestionDetailPage />} />
  <Route path="/stats" element={<StatsPage />} />
</Routes>
```

### Protected Routes

```typescript
function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}
```

If the user isn't logged in, they're redirected to `/login`. After login, they're redirected back (React Router handles this with `Navigate`).

---

## 39. Styling

### Approach

LabAssist uses **plain CSS** (no CSS-in-JS, no Tailwind, no styled-components). All styles are in `src/styles/global.css`.

### Why Plain CSS?

- Simple project — no need for a CSS framework
- Easy to customize
- No build step overhead
- Small bundle size

### Key CSS Classes

| Class | Used By |
|-------|---------|
| `.navbar` | Navbar component |
| `.main-content` | App main area |
| `.questions-list-page`, `.questions-grid` | Questions list |
| `.question-card` | QuestionCard |
| `.question-detail-page`, `.question-full` | Question detail |
| `.answers-section`, `.answer-card` | AnswerCard |
| `.ask-question-page`, `.similar-questions` | Ask question form |
| `.ta-queue-page`, `.flagged-list`, `.flagged-card` | TA queue |
| `.stats-page`, `.stats-grid`, `.stat-card` | Stats dashboard |
| `.login-page`, `.register-page` | Auth forms |
| `.form-group`, `.error`, `.loading` | Shared form styles |

---

## 40. Docker Setup

### Development Stack (`docker-compose.yml`)

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    ports: ["5433:5432"]
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: labassist
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]

  backend:
    build:
      context: ./backend
    ports: ["8000:8000"]
    volumes:
      - ./backend:/app          # Hot-reload source code
      - model_cache:/root/.cache/huggingface  # Cache embedding model
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy

  frontend:
    build:
      context: ./frontend
    ports: ["80:5173"]          # Maps container's 5173 to host's 80
    volumes:
      - ./frontend:/app         # Hot-reload source code
      - /app/node_modules       # Don't overwrite node_modules
    depends_on:
      - backend
```

**Key points:**
- **PostgreSQL port 5433 on host** (to avoid conflict with local PostgreSQL on 5432)
- **Volume mounts** enable hot-reload: edit code on host → container sees changes immediately
- **Model cache volume** prevents re-downloading the embedding model on every rebuild
- **Health check** ensures backend doesn't start before database is ready

### Production Stack (`docker-compose.prod.yml`)

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    restart: unless-stopped
    # ... (same as dev but with prod credentials)
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod  # Optimized build
    restart: unless-stopped
    env_file: .env.prod
    # No volume mounts (built into image)
    # No port mapping (only accessible via internal network)
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod  # Nginx serving built files
    restart: unless-stopped
    ports: ["80:80", "443:443"]
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:80"]
```

**Key differences from dev:**
- **Multi-stage builds** — smaller images, no dev dependencies
- **No volume mounts** — code is baked into the image
- **Restart policies** — `unless-stopped` means services auto-restart on crash
- **Health checks** — automatic monitoring of all services
- **Network isolation** — backend and frontend on separate networks (backend-net, frontend-net)

---

## 41. Development vs Production

| Aspect | Development | Production |
|--------|-------------|------------|
| **Docker Compose file** | `docker-compose.yml` | `docker-compose.prod.yml` |
| **Env file** | `.env` | `.env.prod` |
| **Backend Dockerfile** | `Dockerfile` (hot-reload) | `Dockerfile.prod` (2 workers) |
| **Frontend Dockerfile** | `Dockerfile` (Vite dev) | `Dockerfile.prod` (Nginx) |
| **Code updates** | Volume mounts (instant) | Rebuild image |
| **Logging** | Colored console | JSON |
| **Log level** | DEBUG | WARNING |
| **CORS** | `http://localhost` | `https://your-domain.com` |
| **PyTorch** | CPU-only (~200MB) | Full install from requirements.txt |
| **Workers** | 1 uvicorn (with --reload) | 2 uvicorn workers |
| **Hot-reload** | Yes | No |
| **Restart policy** | None | `unless-stopped` |

---

## 42. Reverse Proxy (Nginx)

### How It Works

In production, the **frontend container runs Nginx**, which serves a dual purpose:

1. **Serves static files** — the built React application from `vite build`
2. **Reverse proxies `/api/*`** — forwards API requests to the backend container

This eliminates the need for a separate reverse proxy (like Caddy).

### Production Nginx Configuration

The Nginx config is baked into `frontend/Dockerfile.prod`:

```nginx
server {
    listen 80;
    server_name _;

    # API proxy to backend
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SPA fallback — serve static files, fall back to index.html
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;
    gzip_min_length 256;
}
```

**Key directives:**
- `proxy_pass http://backend:8000` — forwards `/api/*` to the backend container via Docker DNS
- `try_files $uri $uri/ /index.html` — enables React Router client-side routing
- `proxy_set_header` — passes the original request headers so the backend sees the real client IP and protocol

### Development vs Production

| Environment | Reverse Proxy | How |
|-------------|--------------|-----|
| Development | Vite dev server proxy | `vite.config.ts` proxies `/api` → `http://localhost:8000` |
| Production | Nginx in frontend container | `Dockerfile.prod` builds Nginx config into the image |

### Adding HTTPS

If you need HTTPS, you have two options:

1. **External reverse proxy**: Put Caddy, Nginx, or Traefik **on the host** in front of the Docker stack. It handles TLS termination and forwards HTTP to the frontend container.
2. **External load balancer**: Use a cloud load balancer (AWS ALB, GCP LB, etc.) that terminates TLS and forwards to your server.

The application itself doesn't need any code changes for HTTPS — just set `CORS_ORIGINS` to `https://your-domain.com`.

---

## 43. Environment Variables

### Complete Variable Reference

| Variable | Type | Default | Required | Description |
|----------|------|---------|----------|-------------|
| `DATABASE_URL` | string | `postgresql+asyncpg://postgres:postgres@postgres:5432/labassist` | Yes | Async PostgreSQL connection string |
| `LLM_API_BASE` | string | `https://api.qwen.ai/v1` | Yes | Base URL for the LLM API (OpenAI-compatible `/chat/completions` endpoint) |
| `LLM_API_KEY` | string | *(empty)* | No | API key for LLM authentication (may be empty if proxy handles auth) |
| `SECRET_KEY` | string | `change-me-to-a-random-string` | Yes | JWT signing secret — **must be changed in production** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | int | `60` | No | JWT token lifetime in minutes |
| `CORS_ORIGINS` | string | `http://localhost:3000` | Yes | Comma-separated list of allowed CORS origins (e.g., `http://localhost,https://example.com`) |
| `APP_ENV` | string | `development` | Yes | Application environment: `development` or `production` |
| `LOG_LEVEL` | string | `INFO` | No | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Generating a SECRET_KEY

```bash
openssl rand -hex 32
# Output: a1b2c3d4e5f6... (64 hex characters = 32 bytes)
```

### LLM_API_BASE Format

The URL must point to an OpenAI-compatible endpoint. The backend will call `{LLM_API_BASE}/chat/completions`.

```
# qwen-code-api proxy
LLM_API_BASE=http://host.docker.internal:8080/v1

# Ollama
LLM_API_BASE=http://host.docker.internal:11434/v1

# Direct Qwen API (if available)
LLM_API_BASE=https://api.qwen.ai/v1
```

---

## 44. Local Development Setup

### Step-by-Step

```bash
# 1. Prerequisites
docker --version           # Should be 24+
docker compose version     # Should be 2+

# 2. Clone
git clone <repo-url>
cd LabAssist

# 3. Start Qwen Code API proxy
cd qwen-code-api
cp .env.example .env
# Edit .env with your Qwen OAuth credentials
docker compose up -d --build
cd ..

# 4. Configure LabAssist
cp .env.example .env
# Edit .env:
#   LLM_API_BASE=http://host.docker.internal:8080/v1
#   SECRET_KEY=<random-string>

# 5. Start LabAssist
docker compose up -d --build

# 6. Seed database
docker compose exec backend python -m seed

# 7. Open browser → http://localhost
#    Login: admin / admin123
```

### Hot-Reload Workflow

- **Backend**: Edit any `.py` file → uvicorn auto-reloads → changes appear in ~1 second
- **Frontend**: Edit any `.tsx` file → Vite HMR updates → changes appear instantly
- **Database schema**: Edit `models.py` → create migration → run migration

---

## 45. Debugging

### Backend Debugging

**View logs:**
```bash
docker compose logs -f backend
```

**Enable SQL logging:**
In development, `echo=True` in `create_async_engine()` logs every SQL query. Set `APP_ENV=development` in `.env`.

**Test RAG pipeline:**
```bash
docker compose exec backend python -m test_rag
```

**Check embedding model:**
```bash
docker compose exec backend python -c "
from app.services.embeddings import embed_text
print(embed_text('test')[:5])  # First 5 dimensions
"
```

### Frontend Debugging

**Open browser dev tools:**
- **Network tab**: Check API requests and responses
- **Console tab**: Check for JavaScript errors
- **React Dev Tools**: Inspect component tree and state

**Vite dev server logs:**
```bash
docker compose logs -f frontend
```

### Database Debugging

**Connect to PostgreSQL:**
```bash
docker compose exec postgres psql -U postgres -d labassist

# Useful queries:
SELECT * FROM "user";               -- List users
SELECT id, title, status FROM question ORDER BY created_at DESC LIMIT 10;
SELECT COUNT(*) FROM lab_doc;       -- How many doc chunks?
```

**Check pgvector extension:**
```sql
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### Debugging the RAG Pipeline

**Step-by-step:**
```python
# Inside the backend container
docker compose exec backend python

>>> from app.services.embeddings import embed_text
>>> from app.services.rag import extract_lab_numbers, retrieve_context, build_prompt, call_llm, parse_llm_response
>>> from app.config import settings
>>> import asyncio

# Test embedding
>>> embed_text("How do lists work?")[:5]
[0.023, -0.145, 0.089, 0.012, -0.067]

# Test lab number extraction
>>> extract_lab_numbers("I'm stuck on lab 3")
[3]

# Test full pipeline (needs database session)
>>> async def test():
...     from app.database import AsyncSessionLocal
...     async with AsyncSessionLocal() as session:
...         answer, confidence, labs = await run_rag_pipeline("Test", "How do lists work?", session)
...         print(f"Answer: {answer[:100]}...")
...         print(f"Confidence: {confidence}")
...         print(f"Labs: {labs}")
>>> asyncio.run(test())
```

---

## 46. Testing

### Test Files

| File | Purpose |
|------|---------|
| `test_rag.py` | Tests embedding + vector search + full RAG pipeline with LLM call |
| `test_rag_integration.py` | Integration tests (requires running database) |
| `test_rag_edge_cases.py` | pytest-based edge case tests (can run without database) |

### Running Tests

```bash
# RAG pipeline test (needs seeded database + LLM API)
docker compose exec backend python -m test_rag

# Edge case tests (pytest)
docker compose exec backend python -m pytest test_rag_edge_cases.py -v

# Only non-integration tests
docker compose exec backend python -m pytest test_rag_edge_cases.py -v -k "not integration"
```

### What's Tested

- Embedding dimension count (384)
- Vector search returns results
- Lab number extraction regex
- Chunking at heading boundaries
- Prompt building with context
- LLM response parsing
- Error handling (timeout, HTTP errors)
- Edge cases: empty questions, very long questions, no lab docs, etc.

---

## 47. Database Migrations Guide

### When to Create a Migration

Every time you modify `backend/app/models/models.py`:
- Adding/removing a column
- Changing a column type
- Adding/removing a table
- Adding indexes or constraints

### How to Create a Migration

```bash
# 1. Edit models/models.py (add your column)

# 2. Generate migration
docker compose exec backend alembic revision --autogenerate -m "add new_column to table"

# 3. Review the generated file in backend/alembic/versions/
#    - Make sure it captures what you intended
#    - Alembic sometimes misses things — review carefully!

# 4. Apply migration
docker compose exec backend alembic upgrade head
```

### Rolling Back

```bash
# Roll back one migration
docker compose exec backend alembic downgrade -1

# Roll back to a specific migration
docker compose exec backend alembic downgrade <migration_id>
```

### Checking Status

```bash
# See which migrations have been applied
docker compose exec backend alembic current

# See pending migrations
docker compose exec backend alembic heads
```

---

## 48. Deployment

See [`DEPLOY.md`](./DEPLOY.md) for the complete deployment guide. Key commands:

### Development
```bash
docker compose up -d --build
docker compose exec backend python -m seed
```

### Production
```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend python -m seed
```

---

## 49. Backup & Restore

### Database Backup

```bash
docker compose exec postgres pg_dump -U postgres labassist > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Database Restore

```bash
# Stop the app
docker compose down

# Start only postgres
docker compose up -d postgres

# Wait for it to be healthy
sleep 10

# Restore
cat backup_20260407_143000.sql | docker compose exec -T postgres psql -U postgres -d labassist

# Restart everything
docker compose up -d
```

### Backup Strategy

For production, set up a **cron job**:
```bash
# /etc/cron.d/labassist-backup
0 2 * * * root docker compose -f /opt/LabAssist/docker-compose.prod.yml exec postgres pg_dump -U postgres labassist > /opt/backups/labassist_$(date +\%Y\%m\%d).sql
```

---

## 50. Monitoring & Health Checks

### Health Check Endpoints

| Service | Check | How to Test |
|---------|-------|-------------|
| Backend | `GET /health` | `curl http://localhost:8000/health` |
| PostgreSQL | `pg_isready` | `docker compose exec postgres pg_isready` |
| Frontend | HTTP GET on `/` | `curl http://localhost` |

### Docker Health Check Status

```bash
docker compose ps
# Shows (healthy), (unhealthy), or starting
```

### What to Monitor

| Metric | How to Check | Alert Threshold |
|--------|-------------|-----------------|
| AI answer success rate | Stats page → AI answers count | Drops significantly |
| Average AI confidence | Stats page → avg confidence | Below 0.3 |
| Response time | Request logs → duration_ms | Consistently > 1000ms |
| Error rate | Request logs → status_code 500 | > 5% of requests |
| Disk usage | `df -h` on the host | > 80% |
| Memory usage | `free -h` on the host | > 80% |

---

## 51. Updating the Application

### Code Update

```bash
cd /opt/LabAssist
git pull
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### Add New Lab Materials

```bash
# From GitHub
docker compose -f docker-compose.prod.yml exec backend python -m seed.ingest_github <url> --lab-number N

# Or add .md files to seed/ directory, rebuild, and re-seed
```

### Update Embedding Model

If you change the embedding model (e.g., to a different sentence-transformers model), you must **re-embed all lab docs**:

```bash
docker compose exec backend python -m embed_docs
```

---

## 52. Common Issues

### Backend Can't Connect to Database

**Symptom**: Backend crashes on startup with "connection refused" error.

**Cause**: PostgreSQL isn't ready yet, or the `DATABASE_URL` is wrong.

**Fix**:
```bash
# Check postgres is running
docker compose ps postgres

# Check the URL in .env matches the compose service name
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/labassist
#                                          ^^^^^^^^ must match service name
```

### AI Answers Never Appear

**Symptom**: Questions stay in "analyzing" forever.

**Possible causes:**
1. **LLM API not reachable**: Check `LLM_API_BASE` in `.env`
2. **No lab docs**: Run `python -m seed`
3. **Background task crashed**: Check backend logs for errors
4. **Embedding model not downloaded**: First call downloads ~80MB — wait a few minutes

**Fix**:
```bash
docker compose logs backend | grep -i "error\|rag\|llm"
```

### Frontend Can't Reach Backend

**Symptom**: API calls return 502 or network errors.

**Fix**:
1. Check backend is running: `curl http://localhost:8000/health`
2. Check Vite proxy config: `frontend/vite.config.ts` → target should be `http://localhost:8000`
3. In production, check Nginx is routing `/api/*` to backend:8000

### CORS Errors

**Symptom**: Browser console shows "Access-Control-Allow-Origin" error.

**Fix**: Set `CORS_ORIGINS` in `.env` to include the exact frontend origin:
```env
CORS_ORIGINS=http://localhost        # Dev
CORS_ORIGINS=https://your-domain.com  # Prod
```

### "Username already exists" on Register

The registration endpoint returns 400 if the username is taken. The frontend catches this and shows "Registration failed" — a more specific error message would be better (improvement opportunity).

---

## 53. Known Limitations

### 1. Background Task No Recovery
If the server shuts down while a background AI task is running, the question stays in "analyzing" status forever. There's no automatic retry. TAs must manually answer these.

**Workaround**: Admin can check for stuck questions:
```sql
SELECT id, title FROM question WHERE status = 'analyzing' AND created_at < NOW() - INTERVAL '5 minutes';
```

### 2. In-Memory Rate Limiting
SlowAPI stores rate limit counters in memory. When the server restarts, all counters reset. This is fine for single-instance deployment but doesn't survive restarts.

**Future improvement**: Use Redis-backed rate limiting.

### 3. No Rate Limiting on Auth Endpoints
`/auth/register` and `/auth/login` are not rate-limited, making them vulnerable to brute-force attacks.

**Future improvement**: Add `@limiter.limit("5/minute")` to auth endpoints.

### 4. `datetime.utcnow` Deprecated
Python 3.12+ deprecates `datetime.utcnow`. The codebase uses it for `created_at` and `updated_at` defaults. It still works but produces naive (timezone-unaware) datetimes.

**Future improvement**: Replace with `datetime.now(timezone.utc)`.

### 5. `question.updated_at` Never Updates
The `updated_at` field has `default_factory=datetime.utcnow` but no `onupdate` handler. It always equals `created_at`.

**Future improvement**: Add `onupdate=datetime.utcnow` or manually update it when the question changes.

### 6. GitHub Ingest Is Interactive
`python -m seed.ingest_github` uses `input()` for overwrite confirmation, which doesn't work in non-interactive Docker environments.

**Workaround**: Pass `--overwrite` logic manually or modify the script.

### 7. No Pagination on Search Results
`GET /api/v1/questions/search` returns all results up to `top_k` without pagination headers.

### 8. Single LLM Model Hardcoded
The model name `coder-model` is hardcoded in `rag.py`. It should be configurable via `settings`.

---

## 54. Edge Cases

### Very Long Questions
If a question body is extremely long (thousands of characters), the RAG pipeline still processes it. The embedding model handles any length (it averages token embeddings), but the LLM prompt might exceed the context window. The 120,000-char limit on context helps but doesn't account for the question text itself.

### No Lab Docs in Database
If the database has no `lab_doc` entries (fresh install without seeding), the retrieval step returns empty context. The LLM then answers from general knowledge with the disclaimer "This is not covered in the lab materials."

### Multiple Lab Numbers Mentioned
If a question says "I don't understand the difference between lab 2 and lab 4", the regex extracts `[2, 4]` and the retrieval queries `WHERE lab_number IN (2, 4)`. Chunks from both labs are retrieved and grouped separately in the prompt.

### AI Answer with 0.0 Confidence
If the LLM API times out or returns an error, the answer text is an error message and confidence is 0.0. The question status is set to `open` → appears in TA queue.

### User Rates Their Own AI Answer
A student can rate any answer, including the AI answer to their own question. The system doesn't prevent this. This is intentional — the student should be able to rate their AI answer.

### Duplicate Ratings
A user can only rate an answer once. If they try to rate again, their existing rating is updated (not duplicated). This is handled by the `existing_rating` check in the `rate_answer` endpoint.

### Concurrent Question Submission
If a user clicks "Post Question" twice rapidly, two questions are created (no duplicate detection on the server). The frontend's duplicate detection (semantic search) helps but doesn't prevent it.

---

## 55. FAQ

### Q: How does the AI know which lab materials to use?
A: It converts your question into numbers (an embedding) and finds the most similar lab document chunks using vector math. If you mention a specific lab number (e.g., "lab 3"), it only searches that lab's content.

### Q: What if the AI gives a wrong answer?
A: Rate it 👎. This flags it for TA review. A TA will see your question in their queue and can provide a corrected answer.

### Q: Can the AI answer questions not related to lab materials?
A: Yes. If no relevant lab docs are found, the AI answers from its general programming knowledge but clearly marks it as "not covered in the lab materials."

### Q: How long does it take to get an AI answer?
A: Typically 5-30 seconds. The time depends on how long the LLM API takes to respond. The `reasoning_time_seconds` field on each answer shows the exact time.

### Q: Can students answer each other's questions?
A: No. Only TAs and admins can add manual answers. Students can only view, post new questions, and rate answers.

### Q: What happens if the LLM API is down?
A: The question is marked as "open" and appears in the TA queue. The student sees a timeout error message.

### Q: How are lab documents added to the system?
A: Two ways:
1. Place `.md` files in `backend/seed/` and run `python -m seed`
2. Run `python -m seed.ingest_github <url>` to import from a GitHub repo

### Q: Is my data secure?
A: Passwords are hashed with bcrypt. JWT tokens expire after 60 minutes. However, the `SECRET_KEY` must be a strong random value in production — the default is insecure.

### Q: Can I use a different LLM?
A: Yes, as long as it provides an OpenAI-compatible `/chat/completions` endpoint. Set `LLM_API_BASE` accordingly. You may also need to update the model name in `rag.py`.

### Q: Why does the frontend poll for AI answers instead of using WebSockets?
A: Simplicity. Polling every 2 seconds is easy to implement and works well for the expected answer time (5-30 seconds). WebSockets would add complexity for marginal benefit.

---

## 56. Tools & Dependencies

### Backend Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | 0.115.0 | Web framework (async, automatic OpenAPI docs, dependency injection) |
| `uvicorn[standard]` | 0.30.6 | ASGI server (serves FastAPI) |
| `sqlmodel` | 0.0.22 | ORM — combines SQLAlchemy + Pydantic for database models |
| `asyncpg` | 0.29.0 | Async PostgreSQL driver (for FastAPI request handlers) |
| `psycopg2-binary` | 2.9.9 | Sync PostgreSQL driver (for Alembic migrations and seed scripts) |
| `alembic` | 1.13.2 | Database migration tool (version control for schema) |
| `pgvector` | 0.3.0 | SQLAlchemy type for pgvector columns |
| `sentence-transformers` | 3.0.1 | Text embedding library (wraps PyTorch) |
| `torch` | 2.5.1+cpu | PyTorch (required by sentence-transformers, CPU-only) |
| `httpx` | 0.27.2 | Async HTTP client (for calling LLM API) |
| `pydantic-settings` | 2.4.0 | Environment variable loading with validation |
| `PyJWT` | 2.9.0 | JWT token creation and validation |
| `bcrypt` | 4.2.0 | Password hashing |
| `slowapi` | 0.1.9 | Rate limiting (per-IP request throttling) |
| `structlog` | 24.4.0 | Structured logging (JSON output in prod, colored in dev) |
| `python-multipart` | 0.0.9 | Form data parsing (required by FastAPI) |
| `greenlet` | — | Required by SQLAlchemy for async support |

### Frontend Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `react` | 18.3.1 | UI component framework |
| `react-dom` | 18.3.1 | React DOM rendering |
| `react-router-dom` | 6.26.1 | Client-side routing |
| `axios` | 1.7.4 | HTTP client with interceptors |
| `react-markdown` | 10.1.0 | Markdown rendering for AI answers |
| `typescript` | 5.5.4 | Type-safe JavaScript |
| `vite` | 5.4.3 | Build tool + dev server |
| `@vitejs/plugin-react` | 4.3.1 | React plugin for Vite (JSX, Fast Refresh) |

### DevOps Tools

| Tool | Purpose |
|------|---------|
| Docker | Containerization |
| Docker Compose | Multi-container orchestration (dev + prod) |
| Nginx (in frontend container) | Reverse proxy + static file serving |
| Alembic | Database migrations |
| pgvector/pgvector:pg16 | PostgreSQL image with pgvector pre-installed |

### qwen-code-api Dependencies

| Package | Purpose |
|---------|---------|
| `uv` | Python package manager (fast pip replacement) |
| `hatchling` | Build backend for pyproject.toml |
| Various | See `qwen-code-api/pyproject.toml` for full list |

---

## 57. Design Decisions

### Why FastAPI?

- **Async native**: The RAG pipeline makes async HTTP calls. FastAPI handles async naturally.
- **Automatic OpenAPI docs**: `/docs` endpoint is free API documentation.
- **Pydantic integration**: Request validation is built-in.
- **Type safety**: Full type hints enable IDE autocomplete and mypy checking.

### Why SQLModel?

SQLModel combines SQLAlchemy table definitions with Pydantic models. Instead of defining tables AND Pydantic schemas separately, you define one model that serves both purposes. **However**, this project still uses separate Pydantic schemas in `schemas.py` for API responses — SQLModel models define database tables only.

### Why PostgreSQL + pgvector?

Using one database for both relational data and vector search simplifies the architecture. Without pgvector, you'd need:
- PostgreSQL for relational data
- A separate vector DB (Pinecone, Milvus, Weaviate) for embeddings

pgvector eliminates the second dependency.

### Why Local Embeddings?

Running `all-MiniLM-L6-v2` locally (in the backend container) means:
- No external API call needed for embeddings
- No per-embedding cost
- No network latency
- Works offline (once the model is downloaded)

The tradeoff is ~500 MB RAM usage and a few seconds for the first load.

### Why Background Tasks Instead of WebSockets?

FastAPI's `BackgroundTasks` is the simplest way to run async work after sending a response. WebSockets would require:
- A WebSocket connection from frontend to backend
- Connection management (reconnect, timeout, cleanup)
- More complex error handling

Polling every 2 seconds is simple, reliable, and perfectly adequate for 5-30 second answer times.

### Why Plain CSS?

The project is small enough that a CSS framework (Tailwind, CSS-in-JS) would add more complexity than value. Plain CSS is:
- Zero dependencies
- Easy to customize
- Small bundle size
- No learning curve

### Why Role Hierarchy (student < ta < admin)?

A numerical hierarchy makes permission checks simple:
```python
if user_role_level >= required_level:
    # Access granted
```

This avoids maintaining a matrix of "which role can do what." Adding a new role is just adding a number.

---

## 58. File Reference

### Complete File Listing with Purpose

#### Root Level
| File | Purpose |
|------|---------|
| `docker-compose.yml` | Development Docker Compose stack |
| `docker-compose.prod.yml` | Production Docker Compose stack |
| `.env.example` | Development environment variable template |
| `.env.prod.example` | Production environment variable template |
| `.gitignore` | Files to exclude from Git |
| `README.md` | User-facing project overview |
| `DEPLOY.md` | Deployment guide |
| `IMPLEMENTATION_PLAN.md` | Feature list and implementation status |
| `WIKI.md` | This file — complete technical documentation |

#### Backend (`backend/`)
| File | Purpose |
|------|---------|
| `app/__init__.py` | Empty Python package marker |
| `app/__main__.py` | `python -m app` entry point (runs uvicorn) |
| `app/config.py` | pydantic-settings Settings singleton |
| `app/database.py` | Async + sync SQLAlchemy engines, `get_session` dependency |
| `app/main.py` | FastAPI app factory, middleware, routers, health check |
| `app/middleware.py` | RequestLoggingMiddleware |
| `app/api/auth.py` | POST /register, POST /login |
| `app/api/questions.py` | Question CRUD + search + background AI |
| `app/api/answers.py` | TA answers + answer rating |
| `app/api/ta_review.py` | TA queue + answer edit/delete + question hide/unhide |
| `app/api/stats.py` | Forum analytics |
| `app/models/models.py` | SQLModel database tables (User, Question, Answer, Rating, LabDoc) |
| `app/models/schemas.py` | Pydantic request/response schemas |
| `app/services/auth.py` | Password hashing + JWT |
| `app/services/chunker.py` | Markdown document chunking |
| `app/services/dependencies.py` | Auth dependencies (`get_current_user`, `require_role`) |
| `app/services/embeddings.py` | EmbeddingService singleton |
| `app/services/logging.py` | structlog configuration |
| `app/services/rag.py` | Full RAG pipeline |
| `alembic.ini` | Alembic configuration |
| `alembic/env.py` | Alembic environment (overrides DB URL from settings) |
| `alembic/versions/*.py` | Migration files (8 total) |
| `seed/__main__.py` | Database seeding (`python -m seed`) |
| `seed/ingest_github.py` | GitHub repo ingestion (`python -m seed.ingest_github`) |
| `seed/lab_*.md` | Lab markdown documents for seeding |
| `Dockerfile` | Dev Docker image |
| `Dockerfile.prod` | Production Docker image |
| `requirements.txt` | Python dependencies |
| `test_rag.py` | RAG pipeline test script |
| `test_rag_integration.py` | Integration tests |
| `test_rag_edge_cases.py` | Edge case tests (pytest) |

#### Frontend (`frontend/`)
| File | Purpose |
|------|---------|
| `src/main.tsx` | React entry point |
| `src/App.tsx` | Router + protected routes + AuthProvider |
| `src/api/client.ts` | Axios API client with JWT interceptor |
| `src/context/AuthContext.tsx` | Auth state management |
| `src/types/index.ts` | TypeScript interfaces |
| `src/components/Navbar.tsx` | Navigation bar |
| `src/components/QuestionCard.tsx` | Question summary card |
| `src/components/AnswerCard.tsx` | Answer card with rating/editing |
| `src/pages/Login.tsx` | Login page |
| `src/pages/Register.tsx` | Registration page |
| `src/pages/QuestionsList.tsx` | Questions list with filters |
| `src/pages/QuestionDetail.tsx` | Question detail with answers |
| `src/pages/AskQuestion.tsx` | New question form with duplicate detection |
| `src/pages/TAQueue.tsx` | TA review queue |
| `src/pages/Stats.tsx` | Analytics dashboard |
| `src/styles/global.css` | Global CSS styles |
| `Dockerfile` | Dev Docker image |
| `Dockerfile.prod` | Production Docker image |
| `package.json` | Node.js dependencies |
| `vite.config.ts` | Vite configuration (dev server + proxy) |
| `tsconfig.json` | TypeScript configuration |
| `index.html` | HTML entry point |

#### qwen-code-api (`qwen-code-api/`)
| File | Purpose |
|------|---------|
| `Dockerfile` | Proxy Docker image |
| `docker-compose.yml` | Proxy Docker Compose |
| `docker-entrypoint.sh` | Container startup script |
| `pyproject.toml` | Python project config |
| `.env.example` | Proxy environment variable template |
| `README.md` | Proxy documentation |
| `plan.md` | Proxy implementation plan |
| `sys-prompt.txt` | Default Qwen Code system prompt |
| `scripts/compare_requests.py` | Dev tool for request comparison |

#### Scripts (`scripts/`)
| File | Purpose |
|------|---------|
| `check-qwen-oauth-expiry.sh` | Cron: warn about Qwen OAuth token expiry |
| `refresh-qwen-oauth.sh` | Cron: refresh Qwen OAuth token |

---

## Appendix: How to Add a New Feature

### Adding a New API Endpoint

1. **Define the model** in `app/models/models.py` (if new table) or modify existing
2. **Create a migration**: `alembic revision --autogenerate -m "description"`
3. **Define request/response schemas** in `app/models/schemas.py` (if needed)
4. **Create the endpoint** in the appropriate `app/api/*.py` file
5. **Register the router** in `app/main.py` (if new router)
6. **Add auth dependencies** (`Depends(get_required_user)`, `Depends(require_role("ta"))`)
7. **Test**: `curl` the endpoint or use the auto-generated docs at `/docs`

### Adding a New Frontend Page

1. **Create the page component** in `src/pages/NewPage.tsx`
2. **Add the route** in `src/App.tsx`
3. **Add navigation link** in `src/components/Navbar.tsx`
4. **Add API methods** in `src/api/client.ts` (if new endpoints)
5. **Add TypeScript types** in `src/types/index.ts` (if new data types)

### Adding a New Environment Variable

1. **Add the field** to `Settings` in `app/config.py`
2. **Update `.env.example`** and `.env.prod.example`
3. **Update DEPLOY.md** and **WIKI.md** documentation
4. **Restart** the backend to pick up the new value

---

*This document was last updated on April 7, 2026. It reflects the actual, deployed implementation.*
