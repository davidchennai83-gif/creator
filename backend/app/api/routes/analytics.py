from app.api.planned import planned_router
router = planned_router("Social analytics", [("GET", "/summary"), ("GET", "/views"), ("GET", "/followers"), ("GET", "/engagement"), ("GET", "/platform-comparison"), ("GET", "/content-performance"), ("GET", "/revenue"), ("GET", "/ai-insights"), ("POST", "/ai-question")])
