"""Public catalogue and owner controls for Tamil Budget Finds (Meesho)."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import finds, finds_agent
from app.api.deps import editor
from app.schemas.common import success

router = APIRouter()


class ProductInput(BaseModel):
    id: str | None = None
    external_id: str | None = None
    title: str = Field(min_length=2, max_length=500)
    title_ta: str = Field(default="", max_length=500)
    category: str = Field(default="General", min_length=1, max_length=100)
    price: float = Field(default=0, ge=0, le=10_000_000)
    mrp: float = Field(default=0, ge=0, le=10_000_000)
    rating: float = Field(default=0, ge=0, le=5)
    orders_count: int = Field(default=0, ge=0)
    return_risk: Literal["low", "medium", "high"] = "low"
    commission_percent: float = Field(default=0, ge=0, le=100)
    commission_amount: float = Field(default=0, ge=0)
    affiliate_url: str = Field(min_length=8, max_length=2000)
    image_url: str = Field(default="", max_length=200_000)
    features: list[str] = Field(default_factory=list, max_length=10)
    cautions: list[str] = Field(default_factory=list, max_length=10)
    active: bool = True
    demo: bool = False


class CsvInput(BaseModel):
    csv: str = Field(min_length=1, max_length=2_000_000)


class ToggleInput(BaseModel):
    active: bool


class AgentPrepareInput(BaseModel):
    day: str | None = None
    force: bool = False
    product_id: str | None = Field(default=None, max_length=80)


class AgentApproveInput(BaseModel):
    run_id: str = Field(min_length=4, max_length=80)
    approved: bool = True


class AgentPublishInput(BaseModel):
    run_id: str = Field(min_length=4, max_length=80)
    platform: Literal["youtube", "facebook", "instagram"] | None = None
    force: bool = False


class AgentLinksInput(BaseModel):
    links: str = Field(min_length=1, max_length=200_000)
    real: bool = False
    category: str = Field(default="General", max_length=100)


class AgentConfigInput(BaseModel):
    enabled: bool | None = None
    auto_prepare: bool | None = None
    prepare_at: str | None = None
    approval_required: bool | None = None
    require_affiliate_link: bool | None = None
    auto_publish: bool | None = None
    auto_mode: bool | None = None
    auto_publish_platforms: list[Literal["youtube", "facebook", "instagram"]] | None = None
    publish_grace_minutes: int | None = Field(default=None, ge=0, le=180)
    max_publish_attempts: int | None = Field(default=None, ge=1, le=10)
    feed_url: str | None = Field(default=None, max_length=2000)
    feed_path: str | None = Field(default=None, max_length=2000)
    feed_sync_at: str | None = None
    platforms: list[Literal["youtube", "facebook", "instagram"]] | None = None


@router.get("/products")
def products(category: str | None = None, q: str | None = None):
    items = finds.list_products(active_only=True, category=category, search=q, public=True)
    return success({"products": items, "categories": finds.categories()})


@router.get("/products/{product_id}")
def product(product_id: str):
    item = finds.get_product(product_id, public=True)
    if not item or not item.get("active"):
        raise HTTPException(404, "Product not found")
    return success(item)


@router.get("/categories")
def product_categories():
    return success(finds.categories())


@router.get("/today")
def today():
    item = finds.today_pick()
    return success(finds.get_product(item["id"], public=True) if item else None)


@router.get("/admin/products")
def admin_products(user=Depends(editor)):
    return success({"products": finds.list_products(), "categories": finds.categories()})


@router.get("/admin/products/{product_id}")
def admin_product(product_id: str, user=Depends(editor)):
    item = finds.get_product(product_id)
    if not item:
        raise HTTPException(404, "Product not found")
    return success(item)


@router.post("/admin/products")
def save_product(data: ProductInput, user=Depends(editor)):
    try:
        item = finds.upsert_product(data.model_dump(), source="manual")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return success(item, "Product saved")


@router.post("/admin/products/{product_id}/toggle")
def toggle_product(product_id: str, data: ToggleInput, user=Depends(editor)):
    item = finds.get_product(product_id)
    if not item:
        raise HTTPException(404, "Product not found")
    try:
        saved = finds.upsert_product({**item, "active": data.active}, source=item.get("source") or "manual")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return success(saved, "Product updated")


@router.delete("/admin/products/{product_id}")
def remove_product(product_id: str, user=Depends(editor)):
    if not finds.delete_product(product_id):
        raise HTTPException(404, "Product not found")
    return success({"id": product_id, "deleted": True})


@router.post("/admin/import")
def import_products(data: CsvInput, user=Depends(editor)):
    try:
        result = finds.import_products(data.csv)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    message = f"Imported {result['imported']} product(s)"
    if result["errors"]:
        message += f"; {len(result['errors'])} row(s) need attention"
    return success(result, message)


@router.post("/admin/orders/import")
def import_orders(data: CsvInput, user=Depends(editor)):
    try:
        result = finds.import_orders(data.csv)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return success(result, f"Imported {result['imported']} order(s)")


@router.get("/admin/orders")
def orders(limit: int = 100, user=Depends(editor)):
    return success(finds.list_orders(limit))


@router.get("/admin/analytics")
def analytics(days: int = 30, user=Depends(editor)):
    return success(finds.analytics(days))


@router.post("/admin/seed-demo")
def seed_demo(user=Depends(editor)):
    return success(finds.seed_demo(), "Demo products ready")


# ---------------------------------------------------------------------------
# Meesho Autopilot — select -> approve -> render -> publish -> track
# ---------------------------------------------------------------------------
@router.get("/admin/agent/status")
def agent_status(day: str | None = None, user=Depends(editor)):
    try:
        return success(finds_agent.status(day))
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.get("/admin/agent/runs")
def agent_runs(limit: int = 20, user=Depends(editor)):
    return success(finds_agent.list_runs(limit))


@router.get("/admin/agent/events")
def agent_events(run_id: str | None = None, limit: int = 30, user=Depends(editor)):
    return success(finds_agent.list_events(run_id, limit))


@router.post("/admin/agent/prepare")
def agent_prepare(data: AgentPrepareInput | None = None, user=Depends(editor)):
    data = data or AgentPrepareInput()
    try:
        return success(finds_agent.prepare(data.day, data.force, data.product_id), "Autopilot selection ready")
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/admin/agent/approve")
def agent_approve(data: AgentApproveInput, user=Depends(editor)):
    try:
        return success(finds_agent.approve(data.run_id, data.approved),
                       "Product approved" if data.approved else "Approval revoked")
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/admin/agent/publish")
def agent_publish(data: AgentPublishInput, user=Depends(editor)):
    try:
        result = finds_agent.publish(data.run_id, data.platform, data.force)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    message = ("Upload started" if result.get("ok") and not result.get("skipped")
               else result.get("skipped") or result.get("blocked") or "Nothing to do")
    return success(result, message)


@router.post("/admin/agent/links")
def agent_links(data: AgentLinksInput, user=Depends(editor)):
    try:
        result = finds_agent.import_links(data.links, real=data.real, category=data.category)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    message = f"Imported {result['imported']} Meesho link(s)"
    if result["error_count"]:
        message += f"; {result['error_count']} line(s) need attention"
    return success(result, message)


@router.post("/admin/agent/config")
def agent_config(data: AgentConfigInput, user=Depends(editor)):
    try:
        return success(finds_agent.save_config(data.model_dump(exclude_none=True)),
                       "Autopilot settings saved")
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/admin/agent/feed/sync")
def agent_feed_sync(user=Depends(editor)):
    try:
        result = finds_agent.sync_feed(force=True)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    message = f"Feed imported {result.get('imported', 0)} product(s)"
    if result.get("error_count"):
        message += f"; {result['error_count']} item(s) need attention"
    return success(result, message)


@router.post("/admin/agent/tick")
def agent_tick(user=Depends(editor)):
    return success(finds_agent.tick())
