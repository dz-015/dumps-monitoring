# Dumps Monitoring

CV-based monitoring system for waste container fill levels at municipal collection sites.

Detects bin overflow events and ground litter via fixed-pole CCTV cameras using a YOLO-based pipeline.
Provides a web dashboard for operators to view sites, alerts, and pickup recommendations.

## Stack

- **Backend** — Python · FastAPI · SQLAlchemy · Alembic · SQLite (Postgres-ready)
- **Frontend** — React · TypeScript · Vite · Leaflet
- **Deploy** — Docker Compose · nginx

## Quick start

```bash
cp .env.example .env
# Edit .env (set SECRET_KEY, DB credentials, etc.)

docker compose up -d
```

Services:
- Frontend — http://localhost:5173
- Backend API — http://localhost:8000
- API docs — http://localhost:8000/docs

## Development

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```
