# Implementation Plan — LabAssist

> **Status: COMPLETE** — This document has been updated to reflect the actual, deployed implementation. All features listed here are live and functional.

## Product Info

| Field | Details |
|-------|---------|
| **Product name** | LabAssist |
| **End-user** | Students taking the course who get stuck on labs |
| **Problem** | Waiting for TA feedback slows down learning; students ask the same recurring questions |
| **Product idea** | An AI-powered Q&A forum where students get instant answers from lab materials, and TAs step in only when needed |
| **Core feature** | Post a question → backend retrieves relevant lab docs via RAG → LLM generates answer → student rates helpfulness → TAs review flagged answers |

---

## Architecture

```
┌─────────────────┐         ┌──────────────────────┐         ┌───────────┐
│   React 18      │  REST   │   FastAPI 0.115      │  HTTP   │  LLM API  │
│  TypeScript     │────────►│   Python 3.12        │────────►│  (Qwen)   │
│  Vite 5         │  /api   │   SQLModel + asyncio │  /v1    │  via      │
│  Axios          │         │   structlog          │         │  qwen-    │
└─────────────────┘         │                      │         │  code-api │
                            │  ┌────────────────┐  │         └───────────┘
                            │  │  RAG Pipeline  │  │
                            │  │  (embed →      │  │
                            │  │   search →     │  │
                            │  │   generate)    │  │
                            │  └───────┬────────┘  │
                            └──────────┼───────────┘
                                       │
                              ┌────────▼──────────┐
                              │   PostgreSQL 16    │
                              │   + pgvector       │
                              │   (relational +    │
                              │    vector search)  │
                              └───────────────────┘
```

### How It Works (End-to-End)

1. Student submits a question through the React UI
2. Frontend proxies `/api/*` to FastAPI backend (Vite dev proxy in dev, Nginx in prod)
3. Backend immediately creates the question with status `analyzing` and returns it to the frontend
4. A FastAPI BackgroundTask runs the RAG pipeline asynchronously:
   - **Embed**: Converts question text to a 384-dimensional vector using `sentence-transformers/all-MiniLM-L6-v2` (runs locally, no external API)
   - **Retrieve**: Searches `lab_doc` table via pgvector cosine similarity. If the question mentions specific lab numbers (e.g., "lab 4"), it filters to only those labs
   - **Generate**: Constructs a prompt with retrieved context and calls the LLM API (Qwen Code via `coder-model`)
   - **Store**: Creates an `Answer` record with `source="ai"`, `confidence` score, and `reasoning_time_seconds`
   - **Update**: Sets the question status to `answered` (if confidence > 0.3) or `open` (if low confidence — goes to TA queue)
5. Frontend polls every 2 seconds while the question is still `open`/`analyzing` to detect when the AI answer appears
6. Student rates the answer 👍/👎 — low-rated answers are flagged for TA review
7. TAs see flagged answers in the TA Queue page and can provide corrected answers

---

## Tech Stack

| Layer | Technology | Version |
|-------|------------|---------|
| **Backend** | FastAPI + SQLModel + Alembic (migrations) | 0.115.0 |
| **Database** | PostgreSQL with pgvector extension | 16 + 0.7.4 |
| **Embeddings** | sentence-transformers (all-MiniLM-L6-v2, local CPU) | 3.0.1 |
| **LLM** | Qwen Code API (via qwen-code-api proxy, OpenAI-compatible) | coder-model |
| **Frontend** | React + TypeScript + Vite + React Router + Axios + react-markdown | React 18.3 |
| **Auth** | JWT tokens (PyJWT), bcrypt password hashing | PyJWT 2.9.0 |
| **Logging** | structlog (JSON in prod, colored console in dev) | 24.4.0 |
| **Rate Limiting** | SlowAPI (in-memory, per-IP) | 0.1.9 |
| **Config** | pydantic-settings + `.env` files | 2.4.0 |
| **Infrastructure** | Docker Compose + Nginx reverse proxy (in frontend container) | Compose v2 |
| **Containerization** | Multi-stage Dockerfiles (dev + prod) | Python 3.12-slim |

---

## Implemented Features

### ✅ Version 1 — Core Feature (COMPLETE)

| # | Feature | Status |
|---|---------|--------|
| 1 | Docker Compose (postgres, backend, frontend with hot-reload) | ✅ |
| 2 | Database models (User, Question, Answer, Rating, LabDoc) | ✅ |
| 3 | Alembic migrations (8 migrations total) | ✅ |
| 4 | pydantic-settings config + `.env.example` + `.env.prod.example` | ✅ |
| 5 | FastAPI CRUD endpoints with JWT auth + role hierarchy (student < ta < admin) | ✅ |
| 6 | SlowAPI rate limiting | ✅ |
| 7 | Database seeding (admin user + lab markdown docs from `seed/` directory) | ✅ |
| 8 | pgvector extension + embedding columns on `lab_doc` and `question` tables | ✅ |
| 9 | sentence-transformers integration (lazy-loaded singleton, CPU-only, Docker-cached) | ✅ |
| 10 | Full RAG pipeline: embed → retrieve (with lab number filtering) → prompt → LLM → parse | ✅ |
| 11 | Background AI answer generation (FastAPI BackgroundTasks) | ✅ |
| 12 | Structured logging (structlog) + error handling middleware + global exception handler | ✅ |
| 13 | React frontend with 7 pages + auth context + 3 shared components | ✅ |
| 14 | Docker health checks + service dependencies | ✅ |

### ✅ Version 2 — Deployed (COMPLETE)

| # | Feature | Status |
|---|---------|--------|
| 1 | TA review queue for 👎 flagged AI answers + low-confidence (status="open") answers | ✅ |
| 2 | Semantic search for similar questions (before posting, with debounced search + similarity %) | ✅ |
| 3 | Stats dashboard (question counts, AI performance, rating quality, top users) | ✅ |
| 4 | Production Docker multi-stage builds + optimized images (CPU-only PyTorch, 2 workers) | ✅ |
| 5 | Deploy on VM with Nginx reverse proxy (in frontend container) | ✅ |
| 6 | Answer editing/deletion (TA can edit/delete own, admin can edit/delete any non-AI) | ✅ |
| 7 | Question hiding/unhiding (admin-only, soft hide from TA queue) | ✅ |
| 8 | AI reasoning time tracking (measured and displayed on answers) | ✅ |
| 9 | Markdown rendering for answers (react-markdown) | ✅ |
| 10 | GitHub repo ingestion script (`python -m seed.ingest_github`) | ✅ |

---

## Database Schema (Actual)

### `user`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, default uuid4 |
| `username` | VARCHAR(50) | unique, indexed, not null |
| `password_hash` | VARCHAR(255) | not null (bcrypt) |
| `role` | VARCHAR | `student` (default) / `ta` / `admin` |
| `created_at` | DATETIME | default utcnow |

### `question`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, default uuid4 |
| `user_id` | UUID | FK → user.id |
| `title` | VARCHAR(200) | not null |
| `body` | TEXT | not null |
| `status` | VARCHAR | `analyzing` / `open` / `answered` / `needs_review` |
| `ai_answer_id` | UUID | FK → answer.id, nullable |
| `hidden` | BOOLEAN | default False |
| `ai_reasoning_time_seconds` | FLOAT | nullable |
| `embedding` | VECTOR(384) | nullable (pgvector, for semantic search) |
| `created_at` | DATETIME | default utcnow |
| `updated_at` | DATETIME | default utcnow |

### `answer`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, default uuid4 |
| `question_id` | UUID | FK → question.id |
| `user_id` | UUID | FK → user.id, nullable (NULL for AI) |
| `body` | TEXT | not null |
| `source` | VARCHAR | `ai` / `ta` / `student` |
| `confidence` | FLOAT | 0.0–1.0, nullable |
| `edited` | BOOLEAN | default False |
| `reasoning_time_seconds` | FLOAT | nullable |
| `created_at` | DATETIME | default utcnow |

### `rating`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, default uuid4 |
| `answer_id` | UUID | FK → answer.id |
| `user_id` | UUID | FK → user.id |
| `helpful` | BOOLEAN | not null |
| `created_at` | DATETIME | default utcnow |

### `lab_doc`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, default uuid4 |
| `lab_number` | INTEGER | not null |
| `title` | VARCHAR | not null |
| `content` | TEXT | not null (chunked, max ~15K chars per chunk) |
| `embedding` | VECTOR(384) | nullable (pgvector) |
| `chunk_index` | INTEGER | 0-based position within original doc |
| `num_chunks` | INTEGER | total chunks the original doc was split into |
| `updated_at` | DATETIME | default utcnow |

---

## API Endpoints (Actual)

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| `GET` | `/health` | — | — | Health check (rate limited: 10/min) |
| `POST` | `/api/v1/auth/register` | — | — | Register new user |
| `POST` | `/api/v1/auth/login` | — | — | Login, returns JWT |
| `POST` | `/api/v1/questions` | Required | any | Create question (triggers AI background answer) |
| `GET` | `/api/v1/questions` | — | — | List questions (paginated, optional status filter) |
| `GET` | `/api/v1/questions/search` | — | — | Semantic search similar questions (by embedding) |
| `GET` | `/api/v1/questions/{id}` | Optional | — | Question detail with all answers + rating counts |
| `POST` | `/api/v1/questions/{id}/answer` | Required | TA+ | TA adds manual answer |
| `POST` | `/api/v1/answers/{id}/rate` | Required | any | Rate answer 👍/👎 (updates question status) |
| `GET` | `/api/v1/ta/flagged` | Required | TA+ | Get AI answers needing review |
| `POST` | `/api/v1/ta/questions/{id}/answer` | Required | TA+ | TA adds answer to flagged question |
| `PUT` | `/api/v1/answers/{id}` | Required | TA+/Admin | Edit answer (TA own, Admin any non-AI) |
| `DELETE` | `/api/v1/answers/{id}` | Required | TA+/Admin | Delete answer (TA own, Admin any non-AI) |
| `PUT` | `/api/v1/questions/{id}/hide` | Required | Admin | Soft-hide question from TA queue |
| `PUT` | `/api/v1/questions/{id}/unhide` | Required | Admin | Unhide question |
| `GET` | `/api/v1/stats` | Optional | — | Forum analytics |

---

## RAG Pipeline (Actual Implementation)

The core AI logic runs inside `backend/app/services/rag.py`. Every new question triggers this pipeline as a FastAPI BackgroundTask.

### Step 1: Embed
- **Input**: `f"{question_title}\n\n{question_body}"`
- **Model**: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, ~80MB, runs on CPU)
- **Service**: `EmbeddingService` singleton with lazy loading (loaded on first use only)
- **Output**: 384-dimensional float vector, stored on the `question.embedding` column

### Step 2: Retrieve
- **Storage**: pgvector `vector(384)` column on `lab_doc` table, cosine distance
- **Query**: `1 - (embedding <=> CAST(:embedding AS vector)) AS similarity`
- **Lab number filtering**: If the question text mentions explicit lab numbers (regex: `\blab\s*#?(\d+)\b`), the query adds a `WHERE lab_number IN (...)` clause. This ensures "Lab 1" questions get Lab 1 content, not Lab 5's Git section.
- **Thresholds**: 
  - `SIMILARITY_THRESHOLD = 0.25` — minimum to include a chunk
  - `STRONG_MATCH_THRESHOLD = 0.35` — above this, chunks are likely relevant
  - When a lab number filter is applied, ALL chunks from filtered labs are accepted (no threshold)
  - Without a filter, only chunks with similarity ≥ 0.35 are included
- **Max docs**: `MAX_DOCS = 20` chunks retrieved
- **Fallback**: If no chunks pass the threshold, context is set to empty and the LLM answers from general knowledge

### Step 3: Generate (Prompt Building)
- **System prompt**: Instructs the LLM to act as a teaching assistant, use provided context, cite lab numbers, and end with a confidence score
- **Context formatting**: Chunks are grouped by lab number, ordered by similarity, and formatted as `### Lab N (part X/Y): Title\n<content>`
- **Size limit**: `MAX_CONTEXT_CHARS = 120,000` (~25K tokens) to avoid upstream 400 errors
- **Truncation**: If context exceeds limit, chunks are truncated at paragraph boundaries

### Step 4: Call LLM
- **API**: POST to `{llm_api_base}/chat/completions` (OpenAI-compatible format)
- **Model**: `coder-model` (configured in qwen-code-api proxy)
- **Parameters**: `temperature=0.3`, `max_tokens=1024`
- **Timeout**: 120 seconds
- **Error handling**: Timeout → returns "⚠️ AI service timed out" message; HTTP error → returns error message with status code

### Step 5: Parse Response
- **Expected format**:
  ```
  ANSWER: <detailed answer text>
  CONFIDENCE: <0.0 to 1.0>
  ```
- **Regex extraction**: `CONFIDENCE:\s*([0-9.]+)` for confidence, `ANSWER:\s*` prefix removal
- **Fallback confidence**: 0.5 if not found
- **Stored**: Answer body, confidence, and `reasoning_time_seconds` (measured wall-clock time)

### Step 6: Update Question
- Question status set to `answered` if confidence > 0.3, otherwise `open` (goes to TA queue)
- Question embedding updated (stored for future semantic search of duplicates)
- AI reasoning time recorded on the question

---

## Frontend Architecture

### Pages (7)
| Page | Route | Description |
|------|-------|-------------|
| `QuestionsList` | `/` | Filterable list of questions with status badges |
| `QuestionDetail` | `/questions/:id` | Full question view with answers, TA reply form, AI polling |
| `AskQuestion` | `/questions/new` | New question form with live duplicate detection |
| `Login` | `/login` | Login form |
| `Register` | `/register` | Registration form with password confirmation |
| `TAQueue` | `/ta/queue` | Flagged AI answers review queue (TA+ only) |
| `Stats` | `/stats` | Forum analytics dashboard |

### Components (3)
| Component | Description |
|-----------|-------------|
| `Navbar` | Top navigation bar with auth-aware links (shows TA Queue for TA+ users) |
| `QuestionCard` | Summary card in the list view with status badge, body preview, AI timing |
| `AnswerCard` | Full answer card with source badge, confidence, markdown rendering, rating buttons, inline editing/deletion |

### State Management
- **Auth**: React Context (`AuthContext`) with `useState` + `localStorage` persistence
- **Token handling**: Axios interceptor automatically attaches `Authorization: Bearer <token>` to all requests
- **API client**: Centralized `api/client.ts` with typed modules: `authApi`, `questionsApi`, `answersApi`, `taApi`, `healthApi`

### Routing
- `react-router-dom` v6 with `BrowserRouter`
- Protected routes for authenticated pages (`/questions/new`, `/ta/queue`)
- Public pages: `/`, `/questions/:id`, `/login`, `/register`, `/stats`

---

## Project Structure

```
LabAssist/
├── backend/                          # FastAPI Python backend
│   ├── app/
│   │   ├── api/                      # API route handlers
│   │   │   ├── auth.py               # POST /register, /login
│   │   │   ├── questions.py          # CRUD + search + background AI
│   │   │   ├── answers.py            # TA answers + rating
│   │   │   ├── ta_review.py          # TA queue + edit/delete/hide
│   │   │   └── stats.py              # Analytics endpoint
│   │   ├── models/
│   │   │   ├── models.py             # SQLModel database tables
│   │   │   └── schemas.py            # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── auth.py               # Password hashing + JWT
│   │   │   ├── chunker.py            # Markdown chunking at heading boundaries
│   │   │   ├── dependencies.py       # Auth dependencies (get_current_user, require_role)
│   │   │   ├── embeddings.py         # EmbeddingService singleton
│   │   │   ├── logging.py            # structlog setup (JSON prod / console dev)
│   │   │   └── rag.py                # Full RAG pipeline
│   │   ├── __init__.py
│   │   ├── __main__.py               # python -m app entry point
│   │   ├── config.py                 # pydantic-settings Settings singleton
│   │   ├── database.py               # Async + sync engines, get_session
│   │   ├── main.py                   # FastAPI app factory + middleware + routers
│   │   └── middleware.py             # RequestLoggingMiddleware
│   ├── alembic/                      # Database migrations
│   │   ├── env.py
│   │   └── versions/                 # 8 migration files
│   ├── seed/                         # Database seeding
│   │   ├── __main__.py               # python -m seed
│   │   ├── ingest_github.py          # python -m seed.ingest_github <url>
│   │   ├── lab_01_intro_to_python.md
│   │   ├── lab_02_data_structures.md
│   │   └── lab_03_file_io.md
│   ├── Dockerfile                    # Dev: hot-reload, all deps
│   ├── Dockerfile.prod               # Prod: multi-stage, 2 workers
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── test_rag.py                   # RAG pipeline test script
│   ├── test_rag_integration.py       # Integration tests
│   └── test_rag_edge_cases.py        # Edge case tests (pytest)
├── frontend/                         # React TypeScript frontend
│   ├── src/
│   │   ├── api/
│   │   │   └── client.ts             # Axios API client with JWT interceptor
│   │   ├── context/
│   │   │   └── AuthContext.tsx       # Auth state management
│   │   ├── components/
│   │   │   ├── Navbar.tsx
│   │   │   ├── QuestionCard.tsx
│   │   │   └── AnswerCard.tsx
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── Register.tsx
│   │   │   ├── QuestionsList.tsx
│   │   │   ├── QuestionDetail.tsx
│   │   │   ├── AskQuestion.tsx
│   │   │   ├── TAQueue.tsx
│   │   │   └── Stats.tsx
│   │   ├── types/
│   │   │   └── index.ts              # TypeScript interfaces
│   │   ├── styles/
│   │   │   └── global.css            # Global CSS styles
│   │   ├── App.tsx                   # Router + protected routes
│   │   └── main.tsx                  # React entry point
│   ├── Dockerfile                    # Dev: Vite hot-reload
│   ├── Dockerfile.prod               # Prod: Nginx static serving
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts                # Vite config with /api proxy
│   └── index.html
├── qwen-code-api/                    # Qwen OAuth proxy (vendored)
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── pyproject.toml
│   └── ...                           # (separate project, see its own README)
├── scripts/                          # Operational scripts
│   ├── check-qwen-oauth-expiry.sh    # Cron: warn about token expiry
│   └── refresh-qwen-oauth.sh         # Cron: refresh Qwen OAuth token
├── docker-compose.yml                # Dev stack (postgres, backend, frontend)
├── docker-compose.prod.yml           # Prod stack (optimized builds)
├── .env.example                      # Dev env template
├── .env.prod.example                 # Prod env template
├── IMPLEMENTATION_PLAN.md            # This file
├── README.md                         # User-facing documentation
├── DEPLOY.md                         # Deployment guide
├── WIKI.md                           # Complete technical documentation
└── .gitignore
```

---

## Role Hierarchy

| Role | Permissions |
|------|-------------|
| **student** (0) | Post questions, rate answers, view all content |
| **ta** (1) | All student perms + add manual answers, edit/delete own answers, view TA queue |
| **admin** (2) | All TA perms + edit/delete any non-AI answers, hide/unhide questions from TA queue |

---

## Deployment

### Development
```bash
cp .env.example .env
docker compose up -d --build
```
- PostgreSQL on port 5433 (host)
- Backend on port 8000 (host)
- Frontend on port 5173 (container), proxied to port 80 (host)
- Vite dev proxy forwards `/api/*` to `http://localhost:8000`
- Hot-reload for both backend and frontend

### Production
```bash
cp .env.prod.example .env.prod
docker compose -f docker-compose.prod.yml up -d --build
```
- Multi-stage Docker builds (optimized images)
- 2 backend workers (uvicorn)
- Nginx serves frontend static files + reverse proxies `/api/*` to backend
- Health checks with restart policies

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| AI generates incorrect answers | Confidence score + rating system + TA review queue for flagged answers |
| LLM API is slow or down | 120s timeout, fallback error message, question sent to TA queue |
| No relevant lab docs found | LLM answers from general knowledge, clearly marked as "not in lab materials" |
| Embedding model too heavy for VM | Lightweight all-MiniLM-L6-v2 (80MB), runs on CPU, cached in Docker volume |
| Background task fails on shutdown | Question stays in "analyzing" — TA can manually answer; no auto-recovery (future improvement) |
| Rate limiting is in-memory | Fine for single-instance; loses state on restart (future: Redis-backed limiter) |
| `datetime.utcnow` deprecated | Used throughout; migration to `datetime.now(timezone.utc)` is non-breaking (future cleanup) |
