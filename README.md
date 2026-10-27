# Creator Business Automation Platform

> A production-ready, scalable Creator Business Automation Platform that starts as a personal content creation tool and evolves into a multi-tenant SaaS product.

## Features

- Tamil video creator (Day of History, Indian Law, How to Make Money) with narration and MP4 export
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

4. Start with Docker (PostgreSQL + Redis + API + web UI):

```bash
docker-compose up -d
```

The stack publishes exactly one entry point: a [Caddy](https://caddyserver.com)
container in front of the internal nginx (SPA + API + Socket.IO proxy). The
default is plain HTTP on `${HTTP_BIND:-127.0.0.1}:80` — right for localhost, LAN
and tunnel setups, where TLS is terminated by the tunnel provider.

> The container image ships the API only: video rendering needs the local setup
> (Node + Playwright + Tamil fonts) and is not available inside Docker. Use the
> local run below for the Video Creator feature.

#### Public HTTPS (Caddy, automatic certificates)

With a real domain, Caddy obtains and renews Let's Encrypt certificates itself —
no certbot, no cert files:

```bash
# in .env
DOMAIN=example.com
HTTP_BIND=0.0.0.0

docker compose -f docker-compose.yml -f docker/docker-compose.https.yml up -d --build
```

Point the domain's A/AAAA record at this host and open ports 80 + 443.
The overlay also flips the hardening switches (`COOKIE_SECURE=true`,
`ALLOW_REGISTRATION=false`, `REQUIRE_REDIS=true`), so create your owner account
while running the plain stack *before* enabling it. Certificate state lives in
the `caddy_data` volume and renews automatically.

The old manual-certificate flow (`docker/docker-compose.prod.yml` +
`nginx/certs/`) is superseded by this; it still works with
`--scale caddy=0` if you maintain certificates by hand.

5. Or run directly:

```bash
# Terminal 1 - Backend (Hypercorn; scheduler runs inside this process)
cd backend && python start.py

# Terminal 2 - Frontend
cd frontend && npm run dev
```

The Celery worker/scheduler modules under `backend/workers` are placeholders for
a future multi-machine setup (`--profile jobs`); day-to-day scheduling is handled
by the backend process itself.

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
├── nginx/            # Internal nginx configuration (SPA + API + Socket.IO)
├── caddy/            # Caddy edge proxy (auto-HTTPS, the published entry point)
├── docker/           # Docker compose overlays (https / legacy manual certs)
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