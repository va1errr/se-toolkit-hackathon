# LabAssist

> AI-powered Q&A forum for lab courses. Instant answers from lab materials via RAG, with TA review for edge cases.

---

## What is LabAssist?

LabAssist is an AI-powered Q&A forum built for students taking lab-based courses. When you're stuck on a lab, you get instant answers sourced from your actual lab materials — not generic AI responses. TAs step in only when the AI can't help.

### How it works

1. **Post a question** — describe what you're stuck on
2. **AI retrieves context** — searches lab docs for the most relevant sections using semantic similarity
3. **Instant answer** — an LLM generates an answer grounded in your lab materials (background task, question shows "🤖 AI is analyzing..." while processing)
4. **Rate the answer** — 👍 or 👎; ratings are persisted and shown as stats
5. **TA review** — low-confidence answers (< 50%) stay "open" and are flagged for TA review

---

## Features

- **RAG-powered answers** — answers are grounded in your actual lab documents, not hallucinated
- **Background AI generation** — instant redirect after posting, answer arrives when ready
- **Markdown rendering** — AI answers render with proper formatting (code blocks, lists, headers, tables)
- **Rating system** — 👍/👎 counts displayed, vote persists across page reloads, can change vote
- **Analyzing status** — pulsing orange badge while AI works
- **Confidence scores** — every AI answer includes a self-assessed confidence level; < 50% shows "⚠️"
- **JWT authentication** — per-user accounts with student/TA/admin roles
- **TA review queue** — flagged AI answers (👎 or low confidence) shown to TAs for manual override
- **Semantic search** — suggests similar questions before posting to reduce duplicates
- **Stats dashboard** — forum analytics: question counts, AI performance, rating quality, top users
- **Hide questions** — admins can soft-hide flagged questions from the TA queue
- **Dockerized** — one command to spin up the full stack locally with health checks
- **GitHub lab ingestion** — `python -m seed.ingest_github <repo>` to add labs from any GitHub repo

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI + SQLModel + Alembic |
| Database | PostgreSQL + pgvector |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2, local) |
| LLM | Qwen Code API (via qwen-code-api proxy or DashScope) |
| Frontend | React + TypeScript + Vite + React Router + Axios + React Markdown |
| Infrastructure | Docker Compose + Caddy |
| Auth | JWT tokens (PyJWT) + bcrypt |
| Logging | structlog (structured JSON) |
| Rate Limiting | SlowAPI |

---

## Architecture

```
┌─────────────┐        ┌──────────────────┐        ┌───────────┐
│   React     │  REST  │   FastAPI        │  HTTP  │  LLM API  │
│  Frontend   │───────►│   Backend        │───────►│  (Qwen)   │
└─────────────┘        │                  │        └───────────┘
                       │  ┌─────────────┐ │
                       │  │  RAG Engine │ │
                       │  │  (embed →   │ │
                       │  │  search →   │ │
                       │  │  generate)  │ │
                       │  └──────┬──────┘ │
                       └─────────┼────────┘
                                 │
                        ┌────────▼────────┐
                        │    PostgreSQL   │
                        │  (relational +  │
                        │   pgvector)     │
                        └─────────────────┘
```

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose v2
- A Qwen LLM source — either:
  - **qwen-code-api** (free via OAuth) — [github.com/va1errr/qwen-code-api](https://github.com/va1errr/qwen-code-api)
  - **DashScope** API key — [dashscope.console.aliyun.com](https://dashscope.console.aliyun.com/)

### 1. Clone the repo

```bash
git clone https://github.com/<your-username>/labassist.git
cd labassist
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
# Database (port 5433 to avoid local PostgreSQL conflict)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/labassist

# LLM (via qwen-code-api proxy — recommended, free)
LLM_API_BASE=http://localhost:8080/v1
LLM_API_KEY=anything

# Or direct DashScope API:
# LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
# LLM_API_KEY=sk-your-key-here

# Auth
SECRET_KEY=change-this-to-a-random-string
ACCESS_TOKEN_EXPIRE_MINUTES=60

# CORS (comma-separated origins)
CORS_ORIGINS=http://localhost:3000
```

### 3. Start all services

```bash
docker compose up -d
```

This starts:
- **PostgreSQL** (with pgvector) on port `5433` (internal 5432)
- **Backend** (FastAPI) on port `8000`
- **Frontend** (React + Vite) on port `3000` (mapped from container's 5173)

### 4. Seed the database

```bash
docker compose exec backend python -m seed
```

### 5. Add lab materials from GitHub

Each repo becomes one lab document:

```bash
docker compose exec backend python -m seed.ingest_github https://github.com/user/lab-1 --lab-number 1
docker compose exec backend python -m seed.ingest_github https://github.com/user/lab-2 --lab-number 2
```

### 6. Open the app

Visit [http://localhost:3000](http://localhost:3000) (Docker) or [http://localhost:5173](http://localhost:5173) (local dev) and start asking questions.

---

## Project Structure

```
labassist/
├── backend/
│   ├── app/
│   │   ├── api/              # API route handlers (auth, questions, answers)
│   │   ├── models/           # SQLModel database models + Pydantic schemas
│   │   ├── services/         # Business logic
│   │   │   ├── auth.py       # JWT tokens + bcrypt password hashing
│   │   │   ├── dependencies.py  # Auth deps (get_current_user, require_role)
│   │   │   ├── embeddings.py # sentence-transformers service
│   │   │   ├── logging.py    # structlog configuration
│   │   │   └── rag.py        # RAG pipeline (embed → retrieve → generate)
│   │   ├── config.py         # pydantic-settings configuration
│   │   ├── database.py       # Async/sync engine + session factory
│   │   ├── main.py           # FastAPI app entry point
│   │   └── middleware.py     # Request logging middleware
│   ├── alembic/              # Database migrations
│   ├── seed/                 # Seed data + GitHub ingestion script
│   ├── embed_docs.py         # CLI to embed existing lab docs
│   ├── test_rag.py           # RAG pipeline test script
│   ├── Dockerfile            # Dev Dockerfile with hot-reload
│   ├── Dockerfile.prod       # Production multi-stage build
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/client.ts     # Axios API client with JWT attachment
│   │   ├── components/       # Reusable UI (Navbar, QuestionCard, AnswerCard)
│   │   ├── context/AuthContext.tsx  # Auth state + JWT persistence
│   │   ├── pages/            # Page views (Login, Register, Questions, Detail, Ask)
│   │   ├── types/index.ts    # TypeScript interfaces
│   │   ├── styles/global.css # Global styles
│   │   ├── App.tsx           # React Router setup
│   │   └── main.tsx          # React entry point
│   ├── Dockerfile            # Dev with hot-reload
│   ├── Dockerfile.prod       # Production multi-stage (nginx for SPA)
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml        # Dev with health checks
├── docker-compose.prod.yml   # Production with multi-stage builds
├── Caddyfile                 # Reverse proxy with auto HTTPS
├── .env.example              # Environment template
├── IMPLEMENTATION_PLAN.md    # Development roadmap
└── README.md
```

---

## API Endpoints

### Public

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/questions` | List questions (filter by `?status=analyzing|open|answered|closed`) |
| `GET` | `/api/v1/questions/{id}` | Get question with all answers |
| `GET` | `/api/v1/search?q=...` | Search similar questions (V2) |
| `GET` | `/api/v1/stats` | Forum analytics (V2) |

### Authenticated

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/questions` | student | Create question (AI answer generated in background) |
| `POST` | `/api/v1/questions/{id}/answer` | TA | TA adds manual answer |
| `POST` | `/api/v1/answers/{id}/rate` | student | Rate answer helpful or not (can change vote) |
| `POST` | `/api/v1/auth/register` | — | Register a new user |
| `POST` | `/api/v1/auth/login` | — | Login, returns JWT token |

### Question statuses

| Status | Meaning |
|--------|---------|
| `analyzing` | AI is processing the answer (background task) |
| `open` | No AI answer yet, or low confidence (< 50%) — needs TA review |
| `answered` | AI provided answer with confidence ≥ 50% |

---

## Database Schema

### `user`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `username` | str | unique, not null |
| `password_hash` | str | not null (bcrypt) |
| `role` | str | student / ta / admin |
| `created_at` | datetime | |

### `question`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → user, not null |
| `title` | str | max 200 chars |
| `body` | str | not null |
| `status` | str | analyzing / open / answered / closed |
| `ai_answer_id` | UUID | FK → answer, nullable |
| `created_at` | datetime | |
| `updated_at` | datetime | |

### `answer`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `question_id` | UUID | FK → question, not null |
| `user_id` | UUID | FK → user, nullable (null for AI) |
| `body` | str | not null |
| `source` | str | ai / ta / student |
| `confidence` | float | nullable (0–1) |
| `created_at` | datetime | |

### `rating`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `answer_id` | UUID | FK → answer, not null |
| `user_id` | UUID | FK → user, not null |
| `helpful` | bool | not null |
| `created_at` | datetime | |

### `lab_doc`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `lab_number` | int | not null |
| `title` | str | not null |
| `content` | str | not null (full text from markdown files) |
| `embedding` | vector(384) | sentence-transformers embedding |
| `updated_at` | datetime | |

---

## RAG Pipeline

The core AI logic runs as a background task after a question is created:

1. **Instant redirect** — question created immediately, status set to "analyzing"
2. **Embed** — question text → 384-dimensional vector via `all-MiniLM-L6-v2` (local)
3. **Retrieve** — cosine similarity search in pgvector, returns top 3 most relevant lab docs
4. **Generate** — prompt built with question + context → LLM call (120s timeout)
5. **Store** — answer saved with source=ai, confidence score, question status updated
6. **Poll** — frontend polls every 2s until AI answer appears

If labs don't contain relevant info, the LLM answers from general knowledge with a disclaimer.
If the LLM fails, a fallback message is stored and the question stays "open" for TA review.

---

## Development

### Run services individually (without Docker)

**PostgreSQL:**

```bash
docker run --name labassist-db -e POSTGRES_PASSWORD=postgres -p 5433:5432 -d pgvector/pgvector:pg16
```

**Backend:**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

### Run Alembic migrations

```bash
cd backend
alembic upgrade head
```

### Seed the database

```bash
cd backend
python -m seed           # Create demo users + default lab docs
python -m embed_docs     # Generate embeddings for existing lab docs
```

### Ingest labs from GitHub

```bash
cd backend
python -m seed.ingest_github https://github.com/user/lab-1 --lab-number 1
python -m seed.ingest_github https://github.com/user/lab-2 --lab-number 2
```

### Run tests

```bash
cd backend
pytest
```

### Test the RAG pipeline

```bash
cd backend
python test_rag.py
```

---

## Deployment

### Production Docker

```bash
docker compose -f docker-compose.prod.yml up -d
```

This builds multi-stage Docker images:
- **Backend**: slim Python image with compiled dependencies
- **Frontend**: Nginx serving static React build
- **PostgreSQL**: pgvector with persistent volume
- **Caddy**: reverse proxy with automatic HTTPS

### VM with Caddy

1. Update `Caddyfile` — replace `yourdomain.com` with your actual domain
2. Set `.env` with production values (`SECRET_KEY`, `DATABASE_URL`, etc.)
3. Run `docker compose -f docker-compose.prod.yml up -d`
4. Caddy auto-provisions HTTPS via Let's Encrypt

### Health checks in production

All services have health checks configured:
- `postgres` → `pg_isready -U postgres`
- `backend` → `curl -f http://localhost:8000/health`
- `frontend` → `curl -f http://localhost:80`
- `caddy` → `curl -f http://localhost:80`

Startup order: `postgres → backend → frontend → caddy`

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| AI generates incorrect answers | Confidence score + rating system + TA can override |
| LLM API is slow or down | 120s timeout, specific error messages (timeout, HTTP error, connection failure) |
| pgvector unavailable on target VM | Fallback to PostgreSQL full-text search |
| No relevant lab docs found | LLM answers from general knowledge, marks answer as low confidence |
| Embedding model too heavy for VM | Lightweight 80MB model, runs on CPU |
| Large lab repos slow down search | Top 3 most relevant docs retrieved, not full database scan |

---

## License

MIT
