"""Growth-agent API.

Read-only for the most part: the agent runs on its own inside the 24x7 loop.
The `tick` and `report` endpoints exist so the behaviour can be inspected and
driven by hand during maintenance.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from app.api.deps import editor, get_current_user
from app.schemas.common import success
from app.growth import agent as growth

router = APIRouter()


class GrowthConfig(BaseModel):
    enabled: Optional[bool] = None
    recover_renders: Optional[bool] = None
    recover_uploads: Optional[bool] = None
    record_kpis: Optional[bool] = None


@router.get("/status")
def status(user=Depends(get_current_user)):
    """Growth KPIs, today's coverage, the current rotation and recent events."""
    return success(growth.status())


@router.get("/report")
def report(day: Optional[str] = None, user=Depends(get_current_user)):
    return success(growth.report(day))


@router.post("/tick")
def tick(user=Depends(editor)):
    """Run one growth pass now (normally happens every minute by itself)."""
    return success(growth.tick())


@router.post("/report")
def write_report(user=Depends(editor)):
    return success(growth.write_report())


@router.post("/config")
def update_config(data: GrowthConfig, user=Depends(editor)):
    return success(growth.save_config(data.model_dump(exclude_none=True)))
