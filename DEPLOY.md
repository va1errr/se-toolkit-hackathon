# Deploy LabAssist on a production VM

## Prerequisites

- Ubuntu 22.04+ VM with Docker and Docker Compose v2 installed
- Domain name pointing to your VM's IP (e.g., `labassist.example.com`)
- Ports 80 and 443 open in firewall

## 1. Prepare the server

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose v2 (usually included with Docker)
docker compose version
```

## 2. Clone the project

```bash
git clone https://github.com/your-username/labassist.git
cd labassist
```

## 3. Configure environment

```bash
cp .env.prod.example .env

# Generate a strong secret key
openssl rand -hex 32
# Paste the output into SECRET_KEY in .env

# Edit .env with your values:
# - POSTGRES_PASSWORD (strong password)
# - SECRET_KEY (from above)
# - CORS_ORIGINS (your domain, e.g., https://labassist.example.com)
# - LLM_API_BASE (your Qwen proxy or DashScope URL)
nano .env
```

## 4. Update Caddyfile

```bash
nano Caddyfile.prod
# Replace "yourdomain.com" with your actual domain
```

## 5. Deploy

```bash
# Build and start all services
docker compose -f docker-compose.prod.yml up -d --build

# Check status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f
```

## 6. Seed the database

```bash
# Wait for all services to be healthy (check with docker compose ps)
docker compose -f docker-compose.prod.yml exec backend python -m seed

# Ingest lab materials from GitHub
docker compose -f docker-compose.prod.yml exec backend python -m seed.ingest_github https://github.com/your-org/lab-1 --lab-number 1
docker compose -f docker-compose.prod.yml exec backend python -m seed.ingest_github https://github.com/your-org/lab-2 --lab-number 2
```

## 7. Verify

```bash
# Check health endpoints
curl http://localhost/health
curl http://localhost/api/v1/questions

# Open in browser
# https://yourdomain.com
```

## Automatic HTTPS

Caddy automatically provisions and renews SSL certificates via Let's Encrypt. No manual configuration needed.

## Maintenance

### Update the app

```bash
cd labassist
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

### View logs

```bash
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f caddy
```

### Backup database

```bash
docker compose -f docker-compose.prod.yml exec postgres pg_dump -U labassist_user labassist > backup_$(date +%Y%m%d).sql
```

### Restore database

```bash
cat backup_20240101.sql | docker compose -f docker-compose.prod.yml exec -T postgres psql -U labassist_user labassist
```
