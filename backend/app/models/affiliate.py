from app.database.base import Base, UUIDMixin
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, Float, ForeignKey, JSON
from datetime import datetime
from app.utils.time import utcnow
from sqlalchemy import Uuid as UUID, Numeric

class AffiliateNetwork(Base, UUIDMixin):
    __tablename__ = "affiliate_networks"

    name = Column(String(100), nullable=False, unique=True)
    api_base_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    oauth_url = Column(String(500), nullable=True)
    scopes = Column(JSON, nullable=True)

class AffiliateProduct(Base, UUIDMixin):
    __tablename__ = "affiliate_products"

    network_id = Column(UUID(as_uuid=True), ForeignKey("affiliate_networks.id"), nullable=False, index=True)
    product_name = Column(String(500), nullable=False)
    category = Column(String(100), nullable=True)
    original_price = Column(Numeric(18, 2), default=0)
    sale_price = Column(Numeric(18, 2), default=0)
    commission_amount = Column(Numeric(18, 2), default=0)
    commission_percent = Column(Numeric(5, 2), default=0)
    affiliate_url = Column(String(2000), nullable=True)
    tracking_id = Column(String(255), nullable=True)
    image_url = Column(String(1000), nullable=True)
    platform = Column(String(50), nullable=True)
    status = Column(String(20), default="ACTIVE")
    last_updated = Column(DateTime, nullable=True)

class AffiliateLink(Base, UUIDMixin):
    __tablename__ = "affiliate_links"

    product_id = Column(UUID(as_uuid=True), ForeignKey("affiliate_products.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    short_url = Column(String(200), nullable=True)
    original_url = Column(String(2000), nullable=True)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    revenue = Column(Numeric(18, 2), default=0)

class AffiliateClick(Base, UUIDMixin):
    __tablename__ = "affiliate_clicks"

    link_id = Column(UUID(as_uuid=True), ForeignKey("affiliate_links.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    timestamp = Column(DateTime, nullable=False, default=utcnow)
    meta_data = Column(JSON, nullable=True)

class AffiliateOrder(Base, UUIDMixin):
    __tablename__ = "affiliate_orders"

    link_id = Column(UUID(as_uuid=True), ForeignKey("affiliate_links.id"), nullable=False, index=True)
    order_id = Column(String(255), nullable=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("affiliate_products.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    amount = Column(Numeric(18, 2), default=0)
    commission = Column(Numeric(18, 2), default=0)
    status = Column(String(20), default="PENDING")

class AffiliateCommission(Base, UUIDMixin):
    __tablename__ = "affiliate_commissions"

    order_id = Column(UUID(as_uuid=True), ForeignKey("affiliate_orders.id"), nullable=False, index=True)
    link_id = Column(UUID(as_uuid=True), ForeignKey("affiliate_links.id"), nullable=False)
    amount = Column(Numeric(18, 2), default=0)
    status = Column(String(20), default="PENDING")
    paid_at = Column(DateTime, nullable=True)
