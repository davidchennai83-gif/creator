import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from redis.asyncio import Redis
from app.config.settings import settings, PROJECT_DIR
from app.database.engine import engine, sync_engine
from app.api.routes import api_router
from app.middleware.error_handler import error_handler_middleware
from app.middleware.rate_limit_middleware import RateLimitMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app):
    from app.video_creator.jobs import recover
    await asyncio.to_thread(recover)
    from app.video_creator.schedules import start_worker
    scheduler_stop, scheduler_thread = start_worker()
    # Schema is managed by Alembic; API docs remain available during database outages.
    try:
        yield
    finally:
        scheduler_stop.set()
        await asyncio.to_thread(scheduler_thread.join, 35)
        await engine.dispose()
        await asyncio.to_thread(sync_engine.dispose)


def create_app():
    app = FastAPI(title="Creator Platform", description="Personal creator workspace. Unimplemented modules return 501.", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url="/api/redoc", lifespan=lifespan)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=[s.strip() for s in settings.ALLOWED_ORIGINS.split(",")], allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type"])
    error_handler_middleware(app)
    app.include_router(api_router)

    @app.get("/health")
    async def health():
        return {"status": "healthy", "server": "hypercorn", "timestamp": datetime.now(timezone.utc).isoformat()}

    @app.get("/ready")
    async def ready():
        checks = {"database": False, "redis": "not_required"}
        try:
            async with asyncio.timeout(3):
                async with engine.connect() as connection:
                    await connection.execute(text("SELECT version_num FROM alembic_version"))
                    await connection.execute(text("SELECT id FROM users LIMIT 1"))
            checks["database"] = True
        except Exception:
            logging.getLogger(__name__).warning("Database readiness failed")
        if settings.REQUIRE_REDIS:
            try:
                async with Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2) as redis:
                    checks["redis"] = bool(await redis.ping())
            except Exception:
                checks["redis"] = False
        healthy = checks["database"] and checks["redis"] is not False
        return JSONResponse({"status": "ready" if healthy else "not_ready", "checks": checks}, status_code=200 if healthy else 503)

    @app.get("/{path:path}", include_in_schema=False)
    async def web(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "API endpoint not found")
        root = (PROJECT_DIR / "frontend" / "dist").resolve()
        target = (root / path).resolve()
        if not target.is_relative_to(root):
            raise HTTPException(404, "Not found")
        if target.is_file():
            return FileResponse(target)
        index = root / "index.html"
        if not index.is_file():
            return JSONResponse({"message": "Frontend build missing. Run setup-local.cmd, then start-local.cmd.", "api_docs": "/api/docs"}, status_code=503)
        if Path(path).suffix:
            raise HTTPException(404, "Asset not found")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return app


app = create_app()
