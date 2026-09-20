"""Windows-safe Hypercorn entry point; works from any working directory."""
import asyncio
import os
from pathlib import Path


def main():
    os.chdir(Path(__file__).resolve().parent)
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    from app.main import app
    from app.config.settings import settings

    config = Config()
    config.bind = [f"{settings.SERVER_HOST}:{settings.SERVER_PORT}"]
    config.accesslog = "-"
    config.errorlog = "-"
    config.graceful_timeout = 30
    config.use_reloader = False
    if settings.TLS_CERTFILE and settings.TLS_KEYFILE:
        config.certfile = settings.TLS_CERTFILE
        config.keyfile = settings.TLS_KEYFILE
    asyncio.run(serve(app, config))


if __name__ == "__main__":
    main()
