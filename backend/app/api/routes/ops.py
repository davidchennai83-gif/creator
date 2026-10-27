from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from app.api.deps import admin
from app.schemas.common import success
from app.ops import daily

router = APIRouter()


class OpsConfig(BaseModel):
    ai_upgrade_enabled: Optional[bool] = None
    backup_enabled: Optional[bool] = None
    daily_report_enabled: Optional[bool] = None


@router.get("/status")
def status(user=Depends(admin)):
    """Last run, today's report, the roadmap and the autonomous-upgrade log."""
    return success(daily.status())


@router.post("/run")
def run(force: bool = True, user=Depends(admin)):
    """Run the daily maintenance cycle now (backup + report + prune)."""
    return success(daily.maybe_run(force=force))


@router.post("/upgrade")
def upgrade(user=Depends(admin)):
    """Launch one unattended self-upgrade session immediately."""
    return success(daily.ai_upgrade("manual"))


@router.post("/config")
def update_config(data: OpsConfig, user=Depends(admin)):
    return success(daily.save_config(data.model_dump(exclude_none=True)))
