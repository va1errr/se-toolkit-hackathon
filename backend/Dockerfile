FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install only non-PyTorch deps first (better caching)
RUN pip install --no-cache-dir \
    fastapi uvicorn sqlmodel asyncpg alembic pgvector \
    pydantic-settings PyJWT bcrypt slowapi structlog python-multipart httpx greenlet

# Install PyTorch CPU-only (much smaller, ~200MB vs 2GB)
RUN pip install --no-cache-dir torch==2.5.1+cpu --index-url https://download.pytorch.org/whl/cpu

# Install sentence-transformers last
RUN pip install --no-cache-dir sentence-transformers

COPY . .

RUN mkdir -p /root/.cache/huggingface

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
