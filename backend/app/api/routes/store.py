from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import editor, get_current_user
from app.schemas.common import success
from app import store

router = APIRouter()


class OrderItem(BaseModel):
    id: str
    qty: int = Field(default=1, ge=1, le=20)


class Customer(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=7, max_length=15)
    address: str = Field(min_length=5, max_length=300)
    city: str = Field(min_length=2, max_length=60)
    pincode: str = Field(min_length=4, max_length=10)


class OrderRequest(BaseModel):
    items: list[OrderItem] = Field(min_length=1, max_length=30)
    customer: Customer
    payment: Literal["upi", "cod"] = "upi"


class ProductRequest(BaseModel):
    id: Optional[str] = None
    kind: Literal["own", "affiliate"] = "own"
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=40)
    price: int = Field(ge=0, le=10_000_000)
    mrp: int = Field(default=0, ge=0, le=10_000_000)
    rating: float = Field(default=4.0, ge=0, le=5)
    reviews: int = Field(default=0, ge=0, le=10_000_000)
    emoji: str = Field(default="🛍️", max_length=8)
    tagline: str = Field(default="", max_length=160)
    highlight: str = Field(default="", max_length=300)
    features: list[str] = Field(default_factory=list, max_length=8)
    delivery_days: int = Field(default=3, ge=1, le=60)
    stock: int = Field(default=0, ge=0, le=1_000_000)
    affiliate_url: str = Field(default="", max_length=1000)
    platform: str = Field(default="", max_length=30)
    published: bool = True


class ShipRequest(BaseModel):
    partner: str = ""
    tracking: str = ""


class SettingsRequest(BaseModel):
    upi_id: Optional[str] = None
    merchant_name: Optional[str] = None
    partner_name: Optional[str] = None
    partner_phone: Optional[str] = None
    amazon_tag: Optional[str] = None
    flipkart_affid: Optional[str] = None


class MetaRequest(BaseModel):
    url: str = Field(min_length=8, max_length=1000)


# ------------------------------------------------------------ shop (customer)

@router.get("/catalog")
def get_catalog(user=Depends(get_current_user)):
    return success({"products": store.catalog()})


@router.post("/orders", status_code=201)
def create_order(data: OrderRequest, user=Depends(get_current_user)):
    try:
        order = store.place_order(
            str(user.id),
            [item.model_dump() for item in data.items],
            data.customer.model_dump(),
            data.payment,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return success(order)


@router.get("/orders")
def list_orders(user=Depends(get_current_user)):
    return success({"orders": store.orders_for(str(user.id))})


@router.post("/meta")
def fetch_meta(data: MetaRequest, user=Depends(editor)):
    return success(store.meta_from_url(data.url))


# ------------------------------------------------------------ settings

@router.get("/settings")
def get_settings(user=Depends(get_current_user)):
    return success(store.settings_get())


@router.post("/settings")
def update_settings(data: SettingsRequest, user=Depends(editor)):
    return success(store.settings_set(data.model_dump(exclude_none=True)))


@router.get("/readiness")
def get_readiness(user=Depends(editor)):
    return success(store.readiness())


# ------------------------------------------------------------ admin

@router.get("/admin/products")
def admin_list_products(user=Depends(editor)):
    return success({"products": store.admin_products()})


@router.post("/admin/products", status_code=201)
def admin_save_product(data: ProductRequest, user=Depends(editor)):
    body = data.model_dump()
    if body["kind"] == "affiliate" and not body["affiliate_url"].startswith(("http://", "https://")):
        raise HTTPException(422, "Affiliate URL must start with http:// or https://")
    if body["kind"] == "own" and body["mrp"] == 0:
        body["mrp"] = body["price"]
    return success(store.save_product(body))


@router.post("/admin/products/{pid}/publish")
def admin_publish(pid: str, published: bool = True, user=Depends(editor)):
    if not store.set_product_published(pid, published):
        raise HTTPException(404, "Product not found")
    return success({"id": pid, "published": published})


@router.delete("/admin/products/{pid}", status_code=204)
def admin_delete_product(pid: str, user=Depends(editor)):
    if not store.delete_product(pid):
        raise HTTPException(404, "Product not found")


@router.get("/admin/orders")
def admin_list_orders(user=Depends(editor)):
    return success({"orders": store.all_orders()})


@router.post("/click/{pid}")
def record_affiliate_click(pid: str, user=Depends(get_current_user)):
    """Log an affiliate-deal click and return the live (tagged) destination URL."""
    product = store.get_product(pid)
    if not product or product.get("kind") != "affiliate":
        raise HTTPException(404, "Affiliate deal not found")
    store.record_click(pid)
    return success({"url": product.get("affiliate_url", "")})


@router.get("/admin/analytics")
def admin_analytics(user=Depends(editor)):
    return success(store.analytics())


@router.post("/admin/orders/{oid}/paid")
def admin_mark_paid(oid: str, user=Depends(editor)):
    order = store.mark_paid(oid)
    if not order:
        raise HTTPException(404, "Order not found")
    return success(order)


@router.post("/admin/orders/{oid}/ship")
def admin_ship(oid: str, data: ShipRequest, user=Depends(editor)):
    try:
        order = store.ship_order(oid, data.partner, data.tracking)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    if not order:
        raise HTTPException(404, "Order not found")
    return success(order)


@router.post("/admin/orders/{oid}/deliver")
def admin_deliver(oid: str, user=Depends(editor)):
    try:
        order = store.deliver_order(oid)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    if not order:
        raise HTTPException(404, "Order not found")
    return success(order)