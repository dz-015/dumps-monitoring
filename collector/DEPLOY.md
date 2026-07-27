# Deployment Guide

## Requirements

- Ubuntu 22.04+ (or any Linux with Docker)
- Docker Engine 24+ and Docker Compose v2
- 2 vCPU, 2-4 GB RAM, 15-20 GB SSD
- Open ports: 8000 (API)
- Yandex Object Storage bucket (S3-compatible)

## Step 1: Install Docker

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
# Re-login after this (exit and ssh again)
```

Verify:
```bash
docker --version
docker compose version
```

## Step 2: Copy project to server

Option A — git:
```bash
git clone <repo-url> ~/waste-monitoring
cd ~/waste-monitoring
```

Option B — scp from local machine:
```bash
scp -r /path/to/waste-monitoring user@server:~/waste-monitoring
```

## Step 3: Configure environment

```bash
cd ~/waste-monitoring
cp .env.example .env
nano .env
```

Change these values for production:
```
POSTGRES_PASSWORD=<strong-random-password>

# Yandex Object Storage credentials
S3_ENDPOINT_URL=https://storage.yandexcloud.net
S3_ACCESS_KEY=<yandex-access-key-id>
S3_SECRET_KEY=<yandex-secret-access-key>
S3_SNAPSHOTS_BUCKET=<your-bucket-name>
S3_REGION=ru-central1

DEBUG=false
LOG_LEVEL=warning
```

## Step 4: Build and start

All production commands use `docker-compose.prod.yml`. The default
`docker-compose.yml` is for local development only (includes MinIO,
bind-mounted sources, hot-reload) and must not be used on the server.

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

First run takes a few minutes (downloading images, building backend).

Check status:
```bash
docker compose -f docker-compose.prod.yml ps
```

All services should show `healthy`. If not:
```bash
docker compose -f docker-compose.prod.yml logs backend
docker compose -f docker-compose.prod.yml logs db
```

## Step 5: Run database migrations

```bash
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

## Step 6: Verify

```bash
# Health check
curl http://localhost:8000/health/
# Expected: {"status":"ok"}

# Swagger UI (open in browser)
# http://<server-ip>:8000/docs
```

## Step 7: Register cameras

Open Swagger UI at `http://<server-ip>:8000/docs`.

POST `/api/v1/cameras/` with body:
```json
{
  "name": "Camera 1",
  "rtsp_url": "rtsp://user:password@ip:port/path"
}
```

Repeat for each camera. The scheduler will automatically start capturing
snapshots every 60 minutes (default).

To test capture immediately, use POST `/api/v1/capture/trigger/`:
```json
{"camera_id": 1}
```

## Common operations

### View logs
```bash
docker compose -f docker-compose.prod.yml logs -f backend        # follow backend logs
docker compose -f docker-compose.prod.yml logs --tail=100 backend # last 100 lines
```

### Restart services
```bash
docker compose -f docker-compose.prod.yml restart backend   # restart one service
docker compose -f docker-compose.prod.yml down && docker compose -f docker-compose.prod.yml up -d  # restart all
```

### Update code
```bash
cd ~/waste-monitoring
git pull  # or scp new files
docker compose -f docker-compose.prod.yml up -d --build     # rebuild backend
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head  # apply new migrations
```

### Backup database
```bash
docker compose -f docker-compose.prod.yml exec db pg_dump -U waste waste_monitoring > backup_$(date +%Y%m%d).sql
```
s