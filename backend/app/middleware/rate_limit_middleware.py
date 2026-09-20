"""Bounded single-process limiter for the personal server. Redis is required for multi-worker deployment."""
from collections import OrderedDict, deque
from time import monotonic
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit=20, window=60):
        super().__init__(app)
        self.buckets = OrderedDict()
        self.limit, self.window = limit, window

    async def dispatch(self, request, call_next):
        if request.method == "POST" and request.url.path.startswith("/api/v1/auth/"):
            key = request.client.host if request.client else "unknown"
            now = monotonic()
            bucket = self.buckets.setdefault(key, deque())
            self.buckets.move_to_end(key)
            while bucket and bucket[0] <= now - self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return JSONResponse({"success": False, "data": None, "message": "Too many attempts. Try again later.", "error": {"code": "429"}}, 429, headers={"Retry-After": str(self.window)})
            bucket.append(now)
            if len(self.buckets) > 10000:
                self.buckets.popitem(last=False)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response
