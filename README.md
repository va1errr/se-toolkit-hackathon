# LabAssist

> **AI-powered Q&A forum for lab courses** — Get instant answers from your lab materials, with TA oversight when it matters.

## What Is LabAssist?

LabAssist is a web application designed for students who get stuck on lab assignments and don't want to wait hours (or days) for a TA to respond. Instead of posting a question and waiting, LabAssist gives you an **instant, context-aware answer** generated from your course's lab materials using AI.

When the AI isn't confident enough, your question automatically goes to a **TA review queue** so a human can step in. TAs can also correct AI answers that students found unhelpful. The result: **faster learning for students, less repetitive work for TAs.**

## Key Features

### For Students
- **Instant AI answers** — Post a question and get a response in seconds, based on your lab materials
- **Duplicate detection** — As you type, LabAssist suggests similar existing questions so you don't repeat yourself
- **Rate answers** — Thumbs up or down to help the system improve and let other students know which answers are reliable
- **Markdown support** — Answers are formatted with code blocks, lists, and headings for readability

### For TAs
- **Review queue** — See AI answers that students rated as unhelpful or that the AI flagged as low-confidence
- **Correct answers** — Add your own answer to any question, which overrides the AI response
- **Edit and manage** — Edit or delete your own answers, or any non-AI answer if you're an admin
- **Stats dashboard** — Monitor forum health: how many questions are being asked, how well the AI performs, which users are most active

### For Admins
- **Manage content** — Hide inappropriate or off-topic questions from the TA queue
- **Full control** — Edit or delete any non-AI answer, manage user roles

## Quick Start

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) v2+ (use `docker compose` with a space, not `docker-compose`)
- A Qwen Code API proxy running (or any OpenAI-compatible API endpoint)

### Run Locally

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd LabAssist

# 2. Configure environment
cp .env.example .env
# Edit .env and set your LLM_API_BASE, LLM_API_KEY, and SECRET_KEY

# 3. Start everything
docker compose up -d --build

# 4. Run database migrations
docker compose exec backend alembic upgrade head

# 5. Ingest your lab materials from a GitHub repository
docker compose exec backend python -m seed.ingest_github \
    https://github.com/your-org/lab-materials --lab-number 1

# 6. (Optional) Seed demo users
docker compose exec backend python -m seed

# 7. Open your browser
# Frontend: http://localhost
# Backend API: http://localhost:8000
# API docs: http://localhost:8000/docs
```

The default admin account after seeding is:
- **Username**: `admin`
- **Password**: `admin123`

## How It Works

1. **Ask a question** — Type your question. LabAssist shows similar questions as you type.
2. **Get an instant answer** — The AI reads your course's lab materials and generates an answer in seconds (via RAG + Qwen LLM).
3. **Rate the answer** — If it's helpful, give it a 👍. If not, 👎 and a TA will see it in their review queue.
4. **TA steps in when needed** — Low-confidence AI answers or 👎-rated answers go to the TA queue for human review.

## Tech Stack (Overview)

| Layer | Technology |
|-------|------------|
| Frontend | React + TypeScript + Vite |
| Backend | FastAPI (Python) |
| Database | PostgreSQL with vector search (pgvector) |
| AI | Retrieval-Augmented Generation (RAG) with local embeddings + Qwen LLM |
| Infrastructure | Docker Compose + Nginx reverse proxy |

See [`WIKI.md`](./WIKI.md) for complete technical details.

## Project Structure

```
LabAssist/
├── backend/              # FastAPI Python backend
├── frontend/             # React TypeScript frontend
├── qwen-code-api/        # Qwen OAuth proxy (vendored)
├── scripts/              # Operational scripts
├── docker-compose.yml    # Development stack
├── docker-compose.prod.yml  # Production stack
├── IMPLEMENTATION_PLAN.md   # Feature roadmap (completed)
├── DEPLOY.md             # Deployment guide
└── WIKI.md               # Complete technical documentation
```

## Production Deployment

See [`DEPLOY.md`](./DEPLOY.md) for step-by-step production deployment instructions.

## Documentation

| File | Purpose |
|------|---------|
| [`README.md`](./README.md) | This file — overview and quick start |
| [`DEPLOY.md`](./DEPLOY.md) | Step-by-step deployment guide |
| [`WIKI.md`](./WIKI.md) | Complete technical documentation (architecture, API, AI/RAG, database, debugging, etc.) |
| [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md) | Feature list and implementation status |

## License

This project is provided as-is for educational and internal use.
