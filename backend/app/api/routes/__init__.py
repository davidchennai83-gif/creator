from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.api.routes.auth import router as auth_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes import video, scheduler, social, customers, audit_logs, settings, payments

api_router = APIRouter(prefix="/api/v1")
from app.video_creator.routes import router as video_creator_router
api_router.include_router(video_creator_router, prefix='/video-creator', tags=['Video Creator'])
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(payments.router, prefix="/payments", tags=["Payments"], dependencies=[Depends(get_current_user)])
for name, module in {"videos": video, "scheduler": scheduler, "social": social, "customers": customers, "audit-logs": audit_logs, "settings": settings}.items():
    api_router.include_router(module.router, prefix=f"/{name}", tags=[name], dependencies=[Depends(get_current_user)])
