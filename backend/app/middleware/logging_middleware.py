from fastapi import Request, HTTPException
from datetime import datetime, timedelta
import time
import logging

logger = logging.getLogger(__name__)

class LoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive=receive)
        start_time = time.time()
        logger.info(f"{request.method} {request.url.path} - START")
        await self.app(scope, receive, send)
        duration = time.time() - start_time
        logger.info(f"{request.method} {request.url.path} - DONE ({duration:.3f}s)")