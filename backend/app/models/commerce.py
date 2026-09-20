from app.database.base import Base, UUIDMixin
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, Float, ForeignKey, JSON, Enum
from datetime import datetime
from app.utils.time import utcnow
from sqlalchemy import Uuid as UUID, Enum as ENUM, Numeric
import enum

class ProductStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    ARCHIVED = "ARCHIVED"

class Product(Base, UUIDMixin):
    __tablename__ = "products"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    workspace_id = Column(UUID(as_uuid=True), nullable=True)
    sku = Column(String(100), unique=True, nullable=False)
    name = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    price = Column(Numeric(18, 2), default=0)
    sale_price = Column(Numeric(18, 2), default=0)
    cost_price = Column(Numeric(18, 2), default=0)
    stock = Column(Integer, default=0)
    status = Column(ENUM(ProductStatus), default=ProductStatus.ACTIVE, nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

class ProductImage(Base, UUIDMixin):
    __tablename__ = "product_images"

    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    image_url = Column(String(1000), nullable=True)
    thumbnail_url = Column(String(1000), nullable=True)
    is_primary = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)

class Inventory(Base, UUIDMixin):
    __tablename__ = "inventory"

    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, unique=True, index=True)
    quantity = Column(Integer, default=0)
    reserved_quantity = Column(Integer, default=0)
    warehouse_location = Column(String(200), nullable=True)
    last_stock_update = Column(DateTime, nullable=True)

class Customer(Base, UUIDMixin):
    __tablename__ = "customers"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    total_orders = Column(Integer, default=0)
    total_spent = Column(Numeric(18, 2), default=0)

class Order(Base, UUIDMixin):
    __tablename__ = "orders"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    status = Column(String(20), default="NEW", nullable=False, index=True)
    total_amount = Column(Numeric(18, 2), default=0)
    currency = Column(String(3), default="INR")
    shipping_address = Column(Text, nullable=True)
    payment_method = Column(String(50), nullable=True)
    shipped_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)

class OrderItem(Base, UUIDMixin):
    __tablename__ = "order_items"

    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Numeric(18, 2), default=0)
    subtotal = Column(Numeric(18, 2), default=0)

class Payment(Base, UUIDMixin):
    __tablename__ = "payments"

    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True)
    amount = Column(Numeric(18, 2), default=0)
    currency = Column(String(3), default="INR")
    provider = Column(String(50), nullable=True)
    provider_payment_id = Column(String(255), nullable=True)
    status = Column(String(20), default="PENDING", nullable=False, index=True)
    meta_data = Column(JSON, nullable=True)
