# Creator Business Automation Platform

> A production-ready, scalable Creator Business Automation Platform that starts as a personal content creation tool and evolves into a multi-tenant SaaS product.

## Features

- Tamil video creator (Day of History, Indian Law) with narration and MP4 export
- Task scheduler for automatic video generation
- Social media links for manual upload
- Android mobile app (Flutter, sign-in only)
- Activity/audit logging

## Architecture

The platform uses a modular, microservices-inspired architecture:

```
React Frontend → FastAPI Backend → PostgreSQL + Redis
                                        ↓
                                   Celery Workers
                                   (Video, AI, Publishing)
                                        ↓
                                   GPU Workers (optional)
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+
- Ollama (for local AI) - optional

### Development Setup

1. Clone the repository
2. Copy `.env.example` to `.env`
3. Install dependencies:

```bash
cd backend
pip install -r requirements.txt

cd frontend
npm install
```

4. Start with Docker:

```bash
docker-compose up -d
```

5. Or run directly:

```bash
# Terminal 1 - Backend
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend && npm run dev

# Terminal 3 - Worker
cd backend && python -m app.workers.worker

# Terminal 4 - Scheduler
cd backend && python -m app.workers.scheduler
```

### Running Tests

```bash
cd backend && pytest tests/
cd frontend && npm test
```

### Database Migrations

```bash
cd backend && alembic upgrade head
```

## API Documentation

Once the backend is running, visit:
- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`

## Project Structure

```
creator-platform/
├── backend/          # FastAPI backend
├── frontend/         # React frontend
├── mobile/           # Flutter Android app
├── workers/          # Celery workers
├── nginx/            # Nginx configuration
├── docker/           # Docker configuration
├── docs/             # Documentation
└── scripts/          # Utility scripts
```

## Development Phases

| Phase | Focus |
|-------|-------|
| Phase 1 | Foundation (Backend, Frontend, Auth, Docker) |
| Phase 2 | Content Studio, AI, Video |
| Phase 3 | Scheduler, Celery, Notifications |
| Phase 4 | Social Media Integration |
| Phase 5 | Analytics, AI Insights |
| Phase 6 | Affiliate Marketing |
| Phase 7 | E-Commerce |
| Phase 8 | Flutter Android |
| Phase 9 | Production Hardening |

## License

MIT