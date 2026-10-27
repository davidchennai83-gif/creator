from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.api.routes.auth import router as auth_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes import video, scheduler, social, customers, audit_logs, settings, payments, recorder, automation

api_router = APIRouter(prefix="/api/v1")
from app.video_creator.routes import router as video_creator_router
api_router.include_router(video_creator_router, prefix='/video-creator', tags=['Video Creator'])
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(payments.router, prefix="/payments", tags=["Payments"], dependencies=[Depends(get_current_user)])
for name, module in {"videos": video, "scheduler": scheduler, "social": social, "customers": customers, "audit-logs": audit_logs, "settings": settings, "recorder": recorder, "automation": automation}.items():
    api_router.include_router(module.router, prefix=f"/{name}", tags=[name], dependencies=[Depends(get_current_user)])
from app.api.routes.store import router as store_router
api_router.include_router(store_router, prefix="/store", tags=["Store"], dependencies=[Depends(get_current_user)])
from app.api.routes.finds import router as finds_router
api_router.include_router(finds_router, prefix="/finds", tags=["Meesho Finds"])
from app.voice import routes as voice_routes
api_router.include_router(voice_routes.router, prefix="/voice", tags=["Voice"], dependencies=[Depends(get_current_user)])
from app.api.routes.ops import router as ops_router
api_router.include_router(ops_router, prefix="/ops", tags=["Ops"], dependencies=[Depends(get_current_user)])
from app.growth import routes as growth_routes
api_router.include_router(growth_routes.router, prefix="/growth", tags=["Growth"], dependencies=[Depends(get_current_user)])
