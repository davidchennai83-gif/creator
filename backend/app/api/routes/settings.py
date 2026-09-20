from fastapi import APIRouter, Depends
from app.api.deps import get_current_user, unavailable
from app.schemas.common import success
from app.services.auth_service import user_data
from app.config.settings import settings

router = APIRouter()

@router.get("")
async def get_settings(user=Depends(get_current_user)):
    return success({"profile": user_data(user), "ai_provider": settings.AI_PROVIDER, "storage_provider": settings.STORAGE_PROVIDER})

@router.put("")
async def update_settings():
    unavailable()
