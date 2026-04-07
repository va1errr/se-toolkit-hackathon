# Deployment Guide

This guide covers deploying LabAssist in both **development** and **production** environments.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Development Deployment](#development-deployment)
3. [Production Deployment](#production-deployment)
4. [Database Seeding](#database-seeding)
5. [Environment Variables](#environment-variables)
6. [Managing the Application](#managing-the-application)
7. [Troubleshooting](#troubleshooting)
8. [Backup & Restore](#backup--restore)
9. [Updating the Application](#updating-the-application)

---

## Prerequisites

Before deploying LabAssist, ensure the following are installed and configured:

- **Docker** (v24+) — [Install guide](https://docs.docker.com/engine/install/)
- **Docker Compose** (v2+, included with Docker Desktop)
- **Git** — for cloning the repository
- **An LLM API endpoint** compatible with OpenAI's `/chat/completions` format — see below

### Step 0: Start the LLM API

LabAssist needs an LLM to generate answers. You have two options:

#### Option 1: Use the included qwen-code-api proxy (Qwen Code via OAuth)

```bash
cd /root/LabAssist/qwen-code-api
cp .env.example .env
# Edit .env — set your Qwen OAuth credentials
docker compose up -d --build

# Verify it's running
curl http://localhost:8080/health
```

The proxy runs on port 8080. Set `LLM_API_BASE=http://host.docker.internal:8080/v1` in your LabAssist `.env`.

> **Note:** qwen-code-api is a **separate Docker Compose project**. It does NOT start automatically with LabAssist — you must start it yourself first.

#### Option 2: Use any OpenAI-compatible API

If you have Ollama, DashScope, vLLM, or another compatible server, just point `LLM_API_BASE` to it:

```env
# Examples:
LLM_API_BASE=http://host.docker.internal:11434/v1          # Ollama
LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1  # DashScope
```

---

## Managing the LLM API

### If using qwen-code-api

| Action | Command |
|--------|---------|
| **Start** | `cd qwen-code-api && docker compose up -d --build` |
| **Stop** | `cd qwen-code-api && docker compose down` |
| **Restart** | `cd qwen-code-api && docker compose restart` |
| **View logs** | `cd qwen-code-api && docker compose logs -f` |
| **Check health** | `curl http://localhost:8080/health` |

### Token expiry

Qwen OAuth tokens expire. Check and refresh them with:

```bash
bash scripts/check-qwen-oauth-expiry.sh    # Check expiry
bash scripts/refresh-qwen-oauth.sh         # Re-authenticate (may need browser)
```

For full details on qwen-code-api, see [`WIKI.md`](./WIKI.md#27-what-is-qwen-code-api).

---

## Development Deployment

For local development with hot-reload on both frontend and backend.

### Step 1: Clone the Repository

```bash
git clone <your-repo-url>
cd LabAssist
```

### Step 2: Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and set the following:

```env
# Database (default works for Docker Compose)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/labassist

# LLM API — point to your Qwen Code API proxy
LLM_API_BASE=http://host.docker.internal:8080/v1
LLM_API_KEY=your-qwen-api-key

# Security — generate a random key
SECRET_KEY=$(openssl rand -hex 32)

# CORS — allow your dev frontend origin
CORS_ORIGINS=http://localhost

# App environment
APP_ENV=development
LOG_LEVEL=DEBUG
```

> **Note**: On Linux, `host.docker.internal` may not resolve. Use your host machine's IP address instead (e.g., `http://172.17.0.1:8080/v1`). Find it with `ip addr show docker0`.

### Step 3: Start the Stack

```bash
docker compose up -d --build
```

This starts three services:
- **PostgreSQL** (with pgvector extension) — port `5433` on host
- **Backend** (FastAPI with hot-reload) — port `8000` on host
- **Frontend** (React/Vite with hot-reload) — port `80` on host (proxied from container's `5173`)

### Step 4: Verify Services

```bash
# Check all containers are healthy
docker compose ps

# Check backend health
curl http://localhost:8000/health

# Open the frontend
# http://localhost
```

### Step 5: Seed the Database

```bash
docker compose exec backend python -m seed
```

This creates:
- An admin user (`admin` / `admin123`)
- Lab documents from the `seed/` directory (chunked and embedded)

### Step 6: (Optional) Ingest Additional Lab Materials

```bash
# From a GitHub repository
docker compose exec backend python -m seed.ingest_github https://github.com/user/lab-materials --lab-number 4
```

---

## Production Deployment

For production, the stack uses optimized multi-stage builds, and Nginx in the frontend container handles both static file serving and reverse proxying `/api/*` to the backend.

### Step 1: Prepare the Server

Ensure your production server has:
- Docker and Docker Compose installed
- Ports 80 (and 443 if using external HTTPS) open

### Step 2: Clone and Configure

```bash
git clone <your-repo-url> /opt/LabAssist
cd /opt/LabAssist
cp .env.prod.example .env.prod
```

Edit `.env.prod`:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:your-secure-password@postgres:5432/labassist

# LLM API
LLM_API_BASE=http://qwen-code-api:8080/v1
LLM_API_KEY=your-qwen-api-key

# Security — MUST be a strong random key
SECRET_KEY=$(openssl rand -hex 32)

# CORS — your production domain or IP
CORS_ORIGINS=http://your-server-ip

# App environment
APP_ENV=production
LOG_LEVEL=WARNING
```

### Step 3: Start the Production Stack

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

**How it works:** The frontend container runs Nginx, which:
1. Serves the built React static files
2. Reverse proxies `/api/*` requests to the backend container
3. Handles SPA routing (`try_files` fallback to `index.html`)
4. Adds security headers (`X-Frame-Options`, `X-Content-Type-Options`, etc.)

No separate reverse proxy (like Caddy) is needed.

### Step 4: Seed the Database

```bash
docker compose -f docker-compose.prod.yml exec backend python -m seed
```

### Step 6: Verify

```bash
# Check services
docker compose -f docker-compose.prod.yml ps

# Health check
curl http://localhost/health

# Visit your domain in a browser
```

---

## Environment Variables

### Development (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@postgres:5432/labassist` | Async PostgreSQL connection |
| `LLM_API_BASE` | `http://localhost:8080/v1` | Base URL for the LLM API |
| `LLM_API_KEY` | *(empty)* | API key for LLM authentication |
| `SECRET_KEY` | `change-me-to-a-random-string` | JWT signing key — **change in production** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | JWT token lifetime |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins |
| `APP_ENV` | `development` | `development` or `production` |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Production (`.env.prod`)

Same variables, but:
- Use a **strong random** `SECRET_KEY`
- Set `CORS_ORIGINS` to your **production domain**
- Set `APP_ENV=production`
- Set `LOG_LEVEL=WARNING` (or `ERROR`)

---

## Managing the Application

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres
```

### Restart Services

```bash
# Restart everything
docker compose restart

# Restart a single service
docker compose restart backend
```

### Stop Services

```bash
docker compose down
```

### Run Database Migrations

```bash
docker compose exec backend alembic upgrade head
```

### Run Tests

```bash
docker compose exec backend python -m test_rag
docker compose exec backend python -m pytest test_rag_edge_cases.py -v
```

### Access the Database Directly

```bash
# Via psql in the container
docker compose exec postgres psql -U postgres -d labassist

# Or from the host (if port 5433 is mapped)
psql -h localhost -p 5433 -U postgres -d labassist
```

---

## Troubleshooting

### Backend Won't Start

**Symptom**: Backend container exits immediately or shows connection errors.

```bash
# Check logs
docker compose logs backend

# Common causes:
# 1. Can't connect to database — check postgres is running
# 2. LLM API unreachable — verify LLM_API_BASE is correct
# 3. Missing dependencies — rebuild with --no-cache
docker compose build --no-cache backend
```

### Frontend Shows Blank Page

**Symptom**: Frontend loads but API calls fail.

```bash
# Check the Vite proxy config
cat frontend/vite.config.ts
# Ensure '/api' proxy target matches the backend URL

# Check if backend is reachable
curl http://localhost:8000/health
```

### AI Answers Not Appearing

**Symptom**: Questions stay in "analyzing" status forever.

```bash
# Check backend logs for RAG errors
docker compose logs backend | grep -i "rag\|llm\|error"

# Common causes:
# 1. LLM API not configured — check LLM_API_BASE and LLM_API_KEY
# 2. No lab docs in database — run `python -m seed`
# 3. Embedding model not loaded — first call downloads the model (~80MB)
```

### Database Connection Refused

```bash
# Check postgres is running
docker compose ps postgres

# Check port mapping
docker compose port postgres 5432

# Verify credentials match your .env
```

### CORS Errors in Browser

Ensure `CORS_ORIGINS` in your `.env` includes the exact origin (protocol + host + port) of your frontend.

```env
# Example for dev
CORS_ORIGINS=http://localhost

# Example for prod
CORS_ORIGINS=https://your-domain.com
```

---

## Backup & Restore

### Backup Database

```bash
docker compose exec postgres pg_dump -U postgres labassist > backup_$(date +%Y%m%d).sql
```

### Restore Database

```bash
# Stop the app first
docker compose down

# Start only postgres
docker compose up -d postgres

# Restore
docker compose exec -T postgres psql -U postgres -d labassist < backup_20260407.sql

# Restart everything
docker compose up -d
```

### Backup Vector Model Cache

The embedding model is cached in the backend container. If you want to preserve it:

```bash
docker cp labassist-backend-1:/root/.cache/huggingface ./huggingface-backup
```

---

## Updating the Application

### Pull Latest Changes

```bash
cd /opt/LabAssist
git pull
```

### Rebuild and Restart

```bash
docker compose -f docker-compose.prod.yml up -d --build

# Run any new migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### Update Lab Materials

```bash
# Re-seed (only if no data exists)
docker compose -f docker-compose.prod.yml exec backend python -m seed

# Or ingest new labs from GitHub
docker compose -f docker-compose.prod.yml exec backend python -m seed.ingest_github https://github.com/user/new-lab --lab-number 5
```

### Update the Qwen Code API Proxy

```bash
cd qwen-code-api
git pull
docker compose up -d --build
```

---

## Health Checks

All production services have automatic health checks:

| Service | Check | Interval |
|---------|-------|----------|
| PostgreSQL | `pg_isready` | Every 10s |
| Backend | `curl http://localhost:8000/health` | Every 30s |
| Frontend | `wget http://localhost:80` | Every 30s |

Check health status:

```bash
docker compose -f docker-compose.prod.yml ps
```

A service showing `(healthy)` is running correctly. `(unhealthy)` means it's running but failing its health check — check logs for details.
