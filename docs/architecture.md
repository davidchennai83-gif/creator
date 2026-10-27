# Creator Business Automation Platform - Architecture

## 1. System Overview

A modular, scalable Creator Business Automation Platform that starts as a personal content creation tool and evolves into a multi-tenant SaaS product.

## 2. High-Level Architecture

```
                    ┌─────────────────┐
                    │   React Admin   │
                    │     Dashboard   │
                    └────────┬────────┘
                             │ REST API (Axios/Fetch)
                    ┌────────▼────────┐
                    │   FastAPI       │
                    │   Backend       │
                    └───┬─────┬────┬──┘
                        │     │    │
          ┌─────────────┤     │    ├─────────────┐
          │             │     │    │             │
    ┌─────▼─────┐ ┌─────▼──┐ ┌▼────┐ ┌──────────▼──┐
    │PostgreSQL │ │Redis   │ │Workers│ │  Storage    │
    │           │ │        │ │(Celery)│ │(Local/S3)   │
    └───────────┘ └────────┘ └─────┘ └─────────────┘
          │             │    │    │
          │        ┌────▼────┐│    │
          │        │GPU Workers│  │
          │        │(AI/Video)│  │
          └────────┴─────────┘──┘
```

## 3. Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 |
| Frontend | React 18, TypeScript 5, Vite, Tailwind CSS |
| Database | PostgreSQL 15+ |
| Cache/Queue | Redis 7+ |
| Background Jobs | Celery 5 + Redis |
| Video | FFmpeg 6 |
| AI | Ollama-compatible provider abstraction |
| Mobile | Flutter 3+ (Android-first) |
| Auth | JWT (access + refresh), bcrypt |
| Reverse Proxy | Nginx |
| Containerization | Docker + Docker Compose |
| Orchestration | Kubernetes-ready |
| Testing | Pytest, React Testing Library, Playwright |

## 4. Module Architecture

### 4.1 Backend Modules

```
backend/app/
├── main.py                    # FastAPI application factory
├── core/
│   ├── __init__.py
│   ├── security.py            # Password hashing, JWT utilities
│   ├── config.py              # Application configuration
│   ├── events.py              # Domain events
│   └── exceptions.py          # Custom exceptions
├── config/
│   ├── __init__.py
│   ├── settings.py            # Pydantic settings
│   └── constants.py           # Application constants
├── database/
│   ├── __init__.py
│   ├── engine.py              # SQLAlchemy async engine
│   ├── session.py             # Session management
│   └── base.py                # Declarative base
├── models/                    # SQLAlchemy ORM models
│   ├── user.py
│   ├── role.py
│   ├── content.py
│   ├── video.py
│   ├── social.py
│   ├── scheduler.py
│   ├── affiliate.py
│   ├── commerce.py
│   ├── notification.py
│   ├── audit.py
│   ├── ai.py
│   └── system.py
├── schemas/                   # Pydantic request/response schemas
│   ├── user.py
│   ├── content.py
│   ├── video.py
│   ├── social.py
│   ├── scheduler.py
│   ├── affiliate.py
│   ├── commerce.py
│   ├── analytics.py
│   ├── ai.py
│   ├── notification.py
│   └── common.py
├── repositories/              # Data access layer
│   ├── base.py
│   ├── user_repo.py
│   ├── content_repo.py
│   ├── video_repo.py
│   ├── social_repo.py
│   ├── scheduler_repo.py
│   ├── affiliate_repo.py
│   ├── commerce_repo.py
│   └── analytics_repo.py
├── services/                  # Business logic layer
│   ├── auth_service.py
│   ├── content_service.py
│   ├── video_service.py
│   ├── social_service.py
│   ├── scheduler_service.py
│   ├── ai_service.py
│   ├── affiliate_service.py
│   ├── commerce_service.py
│   ├── analytics_service.py
│   ├── notification_service.py
│   ├── audit_service.py
│   └── user_service.py
├── api/
│   ├── __init__.py
│   ├── deps.py                # API dependencies (auth, etc.)
│   └── routes/
│       ├── auth.py
│       ├── users.py
│       ├── dashboard.py
│       ├── content.py
│       ├── video.py
│       ├── scheduler.py
│       ├── social.py
│       ├── analytics.py
│       ├── ai.py
│       ├── affiliate.py
│       ├── products.py
│       ├── orders.py
│       ├── customers.py
│       ├── revenue.py
│       ├── notifications.py
│       ├── audit_logs.py
│       └── settings.py
├── workers/                   # Celery task definitions
│   ├── __init__.py
│   ├── video_worker.py
│   ├── publishing_worker.py
│   ├── analytics_worker.py
│   ├── notification_worker.py
│   ├── affiliate_worker.py
│   ├── commerce_worker.py
│   └── ai_worker.py
├── integrations/              # External service integrations
│   ├── __init__.py
│   ├── base_provider.py       # Abstract base classes
│   ├── ai_provider.py         # AI provider interface
│   ├── ollama_provider.py     # Local Ollama implementation
│   ├── openai_provider.py     # OpenAI implementation (stub)
│   ├── social_provider.py     # Social media interface
│   ├── youtube_provider.py    # YouTube implementation
│   ├── meta_provider.py       # Meta/Facebook implementation
│   ├── tiktok_provider.py     # TikTok implementation
│   ├── payment_provider.py    # Payment interface
│   ├── storage_provider.py    # Storage abstraction
│   └── notification_provider.py # Notification interface
├── middleware/
│   ├── __init__.py
│   ├── auth_middleware.py     # JWT verification
│   ├── rbac_middleware.py     # Role-based access control
│   ├── rate_limit_middleware.py
│   ├── cors_middleware.py
│   ├── logging_middleware.py
│   └── error_handler_middleware.py
└── utils/
    ├── __init__.py
    ├── validators.py
    ├── file_utils.py
    ├── date_utils.py
    ├── pagination.py
    ├── search.py
    └── crypto_utils.py
```

### 4.2 Frontend Modules

```
frontend/src/
├── main.tsx
├── App.tsx
├── routes/
│   └── index.tsx
├── layouts/
│   ├── MainLayout.tsx
│   ├── AuthLayout.tsx
│   └── MobileLayout.tsx
├── components/
│   ├── common/
│   │   ├── Button.tsx
│   │   ├── Modal.tsx
│   │   ├── Drawer.tsx
│   │   ├── Card.tsx
│   │   ├── Table.tsx
│   │   ├── Chart.tsx
│   │   ├── Form.tsx
│   │   ├── Input.tsx
│   │   ├── Select.tsx
│   │   ├── DatePicker.tsx
│   │   ├── FileUploader.tsx
│   │   ├── VideoPlayer.tsx
│   │   ├── Toast.tsx
│   │   ├── Notification.tsx
│   │   ├── Sidebar.tsx
│   │   ├── Topbar.tsx
│   │   ├── Search.tsx
│   │   ├── Pagination.tsx
│   │   └── FilterPanel.tsx
│   └── dashboard/
│       ├── StatsCard.tsx
│       ├── RevenueChart.tsx
│       ├── ContentChart.tsx
│       ├── PlatformChart.tsx
│       ├── TaskList.tsx
│       └── RecentActivity.tsx
├── pages/
│   ├── Login.tsx
│   ├── Register.tsx
│   ├── ForgotPassword.tsx
│   ├── Dashboard.tsx
│   ├── ContentStudio.tsx
│   ├── ContentLibrary.tsx
│   ├── VideoPreview.tsx
│   ├── Calendar.tsx
│   ├── TaskScheduler.tsx
│   ├── SocialMedia.tsx
│   ├── SocialAccountDetail.tsx
│   ├── PublishingCenter.tsx
│   ├── Analytics.tsx
│   ├── AIInsights.tsx
│   ├── AffiliateDashboard.tsx
│   ├── AffiliateProducts.tsx
│   ├── AffiliateLinks.tsx
│   ├── OwnProducts.tsx
│   ├── Inventory.tsx
│   ├── Orders.tsx
│   ├── Customers.tsx
│   ├── Revenue.tsx
│   ├── Notifications.tsx
│   ├── ActivityLogs.tsx
│   └── Settings.tsx
├── hooks/
│   ├── useAuth.ts
│   ├── useApi.ts
│   ├── useDashboard.ts
│   ├── useContent.ts
│   ├── useAnalytics.ts
│   └── useNotifications.ts
├── services/
│   ├── apiClient.ts
│   ├── authService.ts
│   ├── contentService.ts
│   ├── videoService.ts
│   ├── socialService.ts
│   ├── analyticsService.ts
│   ├── aiService.ts
│   ├── affiliateService.ts
│   ├── commerceService.ts
│   └── notificationService.ts
├── stores/
│   ├── authStore.ts
│   ├── contentStore.ts
│   ├── dashboardStore.ts
│   ├── notificationStore.ts
│   └── uiStore.ts
├── types/
│   ├── user.ts
│   ├── content.ts
│   ├── video.ts
│   ├── social.ts
│   ├── analytics.ts
│   ├── affiliate.ts
│   ├── commerce.ts
│   └── common.ts
└── utils/
    ├── formatters.ts
    ├── validators.ts
    ├── constants.ts
    └── dateUtils.ts
```

## 5. Database ERD Design

### 5.1 Core Tables

```sql
-- Users and Roles
users (id UUID PK, email, username, password_hash, display_name, avatar_url, is_active, created_at, updated_at)
roles (id UUID PK, name, description, permissions JSONB)
user_roles (user_id FK, role_id FK)
refresh_tokens (id UUID PK, user_id FK, token_hash, expires_at, created_at, revoked_at)
sessions (id UUID PK, user_id FK, session_token_hash, ip, user_agent, created_at, expires_at, revoked_at)

-- Content
content (id UUID PK, user_id FK, workspace_id FK, title, description, category, status ENUM, language, tags TEXT[], thumbnail_url, duration_seconds, views, likes, comments, shares, created_at, updated_at, published_at, archived_at)
content_scripts (id UUID PK, content_id FK, script_text, hook, cta, title, description, hashtags JSONB, language, version, created_at, updated_at)
content_assets (id UUID PK, content_id FK, asset_type, file_path, file_url, file_size, mime_type, metadata JSONB, created_at)
videos (id UUID PK, content_id FK, input_paths JSONB, intermediate_paths JSONB, final_path, thumbnail_path, subtitle_path, duration, resolution, status ENUM, error_message, created_at, updated_at, completed_at)
video_jobs (id UUID PK, video_id FK, job_type, status ENUM, progress_percent, worker_id, started_at, completed_at, error_message, retry_count, max_retries, created_at)

-- Scheduler
scheduled_tasks (id UUID PK, user_id FK, workspace_id FK, name, content_ref, platform, account_id, cron_expression, schedule_date, schedule_time, timezone, retry_count, priority ENUM, status ENUM, created_at, updated_at, executed_at)
publishing_jobs (id UUID PK, content_id FK, task_id FK, platform, account_id, title, description, hashtags, thumbnail_url, status ENUM, error_message, published_at, created_at, updated_at)

-- Social Media
social_platforms (id UUID PK, name, api_base_url, oauth_url, scopes TEXT[], is_active)
social_accounts (id UUID PK, user_id FK, platform_id FK, account_name, account_id, access_token_encrypted, refresh_token_encrypted, token_expiry, is_connected, last_sync, last_successful_post, created_at, updated_at)
social_posts (id UUID PK, publishing_job_id FK, platform, account_id, post_id, caption, media_url, status ENUM, published_at, created_at, updated_at)
social_analytics (id UUID PK, post_id FK, platform, views, reach, impressions, likes, comments, shares, saves, engagement_rate, collected_at)

-- Affiliate
affiliate_networks (id UUID PK, name, api_base_url, is_active, oauth_url, scopes)
affiliate_products (id UUID PK, network_id FK, product_name, category, original_price, sale_price, commission_amount, commission_percent, affiliate_url, tracking_id, image_url, platform, status, last_updated)
affiliate_links (id UUID PK, product_id FK, user_id FK, short_url, original_url, clicks, conversions, revenue, created_at)
affiliate_clicks (id UUID PK, link_id FK, user_id FK, ip_address, user_agent, timestamp, metadata)
affiliate_orders (id UUID PK, link_id FK, order_id, product_id, user_id, amount, commission, status, created_at)
affiliate_commissions (id UUID PK, order_id FK, link_id FK, amount, status, paid_at, created_at)

-- E-Commerce
products (id UUID PK, user_id FK, workspace_id FK, sku, name, description, category, price, sale_price, cost_price, stock, status ENUM, created_at, updated_at, archived_at)
product_images (id UUID PK, product_id FK, image_url, thumbnail_url, is_primary, sort_order)
inventory (id UUID PK, product_id FK, quantity, reserved_quantity, warehouse_location, last_stock_update)
customers (id UUID PK, user_id FK, email, name, phone, address, total_orders, total_spent, created_at)
orders (id UUID PK, user_id FK, customer_id FK, status ENUM, total_amount, currency, shipping_address, payment_method, created_at, updated_at, shipped_at, delivered_at)
order_items (id UUID PK, order_id FK, product_id FK, quantity, unit_price, subtotal)
payments (id UUID PK, order_id FK, amount, currency, provider, provider_payment_id, status ENUM, metadata JSONB, created_at)

-- Notifications
notifications (id UUID PK, user_id FK, type ENUM, title, message, channel ENUM, metadata JSONB, is_read, read_at, created_at)

-- Audit Logs
audit_logs (id UUID PK, user_id FK, action, entity_type, entity_id, ip_address, user_agent, result, metadata JSONB, timestamp)

-- AI
ai_requests (id UUID PK, user_id FK, provider, model, prompt, response, tokens_used, cost, status, created_at)
ai_usage (id UUID PK, user_id FK, date, total_requests, total_tokens, total_cost, by_provider JSONB)

-- System
system_settings (id UUID PK, setting_key, setting_value, updated_by, updated_at)
```

### 5.2 Indexes and Constraints

```sql
CREATE INDEX idx_content_user_status ON content(user_id, status);
CREATE INDEX idx_content_created_at ON content(created_at DESC);
CREATE INDEX idx_videos_status ON videos(status);
CREATE INDEX idx_social_accounts_platform ON social_accounts(platform_id);
CREATE INDEX idx_scheduled_tasks_status ON scheduled_tasks(status);
CREATE INDEX idx_scheduled_tasks_date ON scheduled_tasks(schedule_date);
CREATE INDEX idx_affiliate_links_clicks ON affiliate_links(clicks);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, is_read);
CREATE UNIQUE INDEX idx_users_email ON users(email);
CREATE UNIQUE INDEX idx_users_username ON users(username);
CREATE UNIQUE INDEX idx_products_sku ON products(sku);
CREATE UNIQUE INDEX idx_affiliate_tracking_id ON affiliate_links(tracking_id);
```

## 6. API Design

### 6.1 Common Response Structure

```json
{
  "success": true,
  "data": {},
  "message": "Success",
  "error": null
}
```

### 6.2 Auth Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/register | Register new user |
| POST | /api/v1/auth/login | Login and get tokens |
| POST | /api/v1/auth/logout | Logout and invalidate tokens |
| POST | /api/v1/auth/refresh | Refresh access token |
| POST | /api/v1/auth/forgot-password | Request password reset |
| POST | /api/v1/auth/reset-password | Reset password |
| GET | /api/v1/auth/me | Get current user |
| PUT | /api/v1/auth/me | Update current user |

### 6.3 Content Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/content | List content (paginated) |
| POST | /api/v1/content | Create content |
| GET | /api/v1/content/{id} | Get content by ID |
| PUT | /api/v1/content/{id} | Update content |
| DELETE | /api/v1/content/{id} | Delete content |
| POST | /api/v1/content/{id}/generate-script | Generate AI script |
| POST | /api/v1/content/{id}/generate-video | Generate video |
| POST | /api/v1/content/{id}/approve | Approve video |
| POST | /api/v1/content/{id}/reject | Reject video |
| POST | /api/v1/content/{id}/publish | Publish content |
| GET | /api/v1/content/{id}/assets | Get content assets |
| POST | /api/v1/content/{id}/upload-asset | Upload asset |

### 6.4 Video Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/videos | List videos |
| GET | /api/v1/videos/{id} | Get video details |
| GET | /api/v1/videos/{id}/status | Get processing status |
| GET | /api/v1/videos/{id}/preview | Get video preview |
| GET | /api/v1/videos/{id}/download | Download video |
| POST | /api/v1/videos/{id}/regenerate | Regenerate video |

### 6.5 Scheduler Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/scheduler | List tasks |
| POST | /api/v1/scheduler | Create task |
| GET | /api/v1/scheduler/{id} | Get task |
| PUT | /api/v1/scheduler/{id} | Update task |
| DELETE | /api/v1/scheduler/{id} | Delete task |
| GET | /api/v1/scheduler/calendar | Calendar view |
| POST | /api/v1/scheduler/{id}/execute | Execute task now |
| GET | /api/v1/scheduler/history | Task history |

### 6.6 Social Media Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/social/platforms | Available platforms |
| GET | /api/v1/social/accounts | Connected accounts |
| POST | /api/v1/social/accounts/connect | Connect account |
| PUT | /api/v1/social/accounts/{id} | Update account |
| DELETE | /api/v1/social/accounts/{id} | Disconnect |
| POST | /api/v1/social/accounts/{id}/sync | Sync |
| POST | /api/v1/social/accounts/{id}/test | Test connection |
| GET | /api/v1/social/posts | Social posts |
| GET | /api/v1/social/analytics | Social analytics |
| POST | /api/v1/social/publish | Publish to social |
| GET | /api/v1/social/publish/{id}/status | Publish status |

### 6.7 Analytics Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/analytics/summary | Dashboard summary |
| GET | /api/v1/analytics/views | Views over time |
| GET | /api/v1/analytics/followers | Followers growth |
| GET | /api/v1/analytics/engagement | Engagement metrics |
| GET | /api/v1/analytics/platform-comparison | Platform comparison |
| GET | /api/v1/analytics/content-performance | Content performance |
| GET | /api/v1/analytics/revenue | Revenue analytics |
| GET | /api/v1/analytics/ai-insights | AI-generated insights |
| POST | /api/v1/analytics/ai-question | Ask AI a question |

### 6.8 Affiliate Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/affiliate/networks | Affiliate networks |
| GET | /api/v1/affiliate/products | Products |
| POST | /api/v1/affiliate/products | Add product |
| GET | /api/v1/affiliate/links | Affiliate links |
| POST | /api/v1/affiliate/links | Create link |
| GET | /api/v1/affiliate/clicks | Click tracking |
| GET | /api/v1/affiliate/commissions | Commissions |
| GET | /api/v1/affiliate/revenue | Revenue report |
| POST | /api/v1/affiliate/promote | Promote product |

### 6.9 E-Commerce Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/products | Products |
| POST | /api/v1/products | Create product |
| PUT | /api/v1/products/{id} | Update product |
| DELETE | /api/v1/products/{id} | Delete product |
| GET | /api/v1/inventory | Inventory |
| GET | /api/v1/customers | Customers |
| GET | /api/v1/orders | Orders |
| POST | /api/v1/orders | Create order |
| PUT | /api/v1/orders/{id}/status | Update order status |
| GET | /api/v1/payments | Payments |
| POST | /api/v1/payments/checkout | Create checkout |
| POST | /api/v1/payments/webhook | Payment webhook |

### 6.10 Other Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/dashboard | Dashboard data |
| GET | /api/v1/notifications | Notifications |
| PUT | /api/v1/notifications/{id}/read | Mark as read |
| GET | /api/v1/audit-logs | Audit logs |
| GET | /api/v1/settings | Settings |
| PUT | /api/v1/settings | Update settings |
| GET | /api/v1/search | Global search |
| GET | /health | Health check |
| GET | /ready | Readiness check |

## 7. Celery/Redis Architecture

```
FastAPI → Redis Queue → Celery Workers

Queues:
├── video_queue     (video generation, FFmpeg processing)
├── publishing_queue (social media publishing)
├── analytics_queue  (analytics aggregation)
├── notification_queue (notifications)
├── affiliate_queue  (affiliate tracking)
├── commerce_queue   (order processing)
└── ai_queue         (AI requests to LLMs)

Worker Configuration:
- Concurrency: 4-8 per worker
- Prefetch: 1
- Task retries: 3 max, exponential backoff
- Rate limiting per queue
- Task result backend: Redis
```

## 8. Social Integration Architecture

```
SocialProvider (Abstract Interface)
├── connect()
├── disconnect()
├── refresh_token()
├── publish(content, account) → PublishingJob
├── get_post_status(job_id)
├── get_analytics(account, date_range)
├── delete_post(post_id)

Implementations:
├── YouTubeProvider (YouTube Data API v3)
├── MetaProvider (Graph API v18+)
├── TikTokProvider (TikTok Business API)
└── TwitterProvider (X/Twitter API v2)
```

## 9. AI Architecture

```
AIProvider (Abstract Interface)
├── generate(prompt, **kwargs) → AIResponse
├── generate_script(topic, language) → Script
├── generate_title(topic) → Title
├── generate_hashtags(topic) → Hashtags
├── generate_cta(topic) → CTA
├── analyze_analytics(question, metrics) → Insights
├── health_check() → bool

Implementations:
├── LocalOllamaProvider (Ollama-compatible local LLM)
├── OpenAIProvider (OpenAI API)
├── AnthropicProvider (Claude API)
└── MockProvider (Testing)
```

## 10. Video Processing Architecture

```
User requests video generation
        ↓
API creates video_job (status: PENDING)
        ↓
Celery task picked up by video_worker
        ↓
FFmpeg pipeline:
  1. Script → Voice (TTS)
  2. Script → Thumbnail (AI or template)
  3. Script → Images/Assets
  4. Voice + Images → Subtitles
  5. Voice + Images + Subtitles + Music → Final Video
        ↓
Worker updates video status → READY_FOR_REVIEW
        ↓
User reviews → Approve/Reject
```

## 11. Security Architecture

```
├── JWT Access Token (15 min expiry)
├── JWT Refresh Token (7 days expiry)
├── bcrypt password hashing (12 rounds)
├── RBAC middleware
├── Rate limiting (Redis-backed)
├── Input validation (Pydantic)
├── SQL injection protection (SQLAlchemy parameterized)
├── XSS protection (React escaping)
├── CSRF protection
├── CORS configuration
├── Token encryption (Fernet for sensitive tokens)
├── File upload validation (size, MIME, extension)
├── Environment variables for secrets
├── Audit logging
└── Secure headers (HSTS, CSP, X-Frame-Options)
```

## 12. Storage Architecture

```
StorageProvider (Abstract Interface)
├── store(file) → file_path
├── retrieve(file_path) → stream
├── delete(file_path)
├── get_url(file_path) → presigned_url
└── exists(file_path) → bool

Implementations:
├── LocalStorageProvider
├── S3CompatibleStorageProvider (MinIO, AWS S3)
└── GCSCompatibleStorageProvider (Google Cloud Storage)
```

## 13. Multi-Tenant Architecture (Future)

```
User
  └── belongs to Workspace(s)
        └── Workspace
              ├── Social Accounts
              ├── Content
              ├── Products
              ├── Orders
              ├── Analytics
              └── Revenue

Each entity has optional workspace_id field.
NULL workspace_id = personal use (version 1)
```

## 14. Docker Architecture

```
docker-compose.yml services:
├── caddy (Edge proxy: HTTP/HTTPS termination + reverse proxy; the only
│          published entry point — auto-HTTPS for a real domain via
│          docker/docker-compose.https.yml)
├── nginx (Internal reverse proxy: SPA static, API, Socket.IO upgrade paths;
│          trusts Caddy's X-Forwarded-For via set_real_ip_from)
├── frontend (React build, served by nginx)
├── backend (FastAPI, port 8000, internal)
├── migrate (alembic upgrade head)
├── worker (Celery worker, profile "jobs")
├── scheduler (Celery beat, profile "jobs")
├── postgres (PostgreSQL 16)
└── redis (Redis 7)
```

## 15. GPU Server Support

```
Architecture:
- API Server: CPU-only, handles HTTP requests
- GPU Workers: Separate Docker service with GPU support
- Communication: Via Redis queues
- GPU Worker capabilities:
  - AI inference (Ollama, image generation)
  - Video rendering (FFmpeg with GPU acceleration)
  - TTS generation
  - Image processing

GPU Server Docker:
- NVIDIA Container Toolkit
- nvidia-docker runtime
- CUDA toolkit
```

## 16. Observability Architecture

```
├── Health check: /health, /ready
├── Application logs: structured JSON logging
├── Worker logs: Celery task logging
├── API logging: Request/response logging middleware
├── Error tracking: Sentry integration architecture
├── Metrics: Prometheus endpoint (future)
├── Database health check
├── Redis health check
└── Alerting: Webhook-based alerting architecture
```

## 17. Development Phases

| Phase | Focus | Duration Estimate |
|-------|-------|-------------------|
| Phase 1 | Foundation: Monorepo, Backend, Frontend, Auth, Docker | 2-3 weeks |
| Phase 2 | Content Studio, AI, Video | 2-3 weeks |
| Phase 3 | Scheduler, Celery, Notifications | 1-2 weeks |
| Phase 4 | Social Media Integration | 2-3 weeks |
| Phase 5 | Analytics, AI Insights | 1-2 weeks |
| Phase 6 | Affiliate Marketing | 1-2 weeks |
| Phase 7 | E-Commerce | 2-3 weeks |
| Phase 8 | Flutter Android | 2-3 weeks |
| Phase 9 | Production Hardening | 1-2 weeks |

## 18. Testing Strategy

```
Backend:
- Unit tests for services, repositories
- API integration tests with TestClient
- Database tests with test containers
- Worker tests with Celery test harness

Frontend:
- Component tests (React Testing Library)
- Hook tests
- Service/API tests
- E2E tests (Playwright)

Critical Workflows Tested:
1. Login → Dashboard
2. Create content → Generate script
3. Generate video → Review
4. Schedule post → Publish
5. Social account connection
6. Analytics sync
7. Affiliate tracking
8. Product order flow
```

## 19. Deployment Strategy

```
Development:
- Docker Compose (local)
- Hot reload for backend and frontend

Staging:
- Docker Compose
- Nginx reverse proxy
- SSL certificates

Production:
- Kubernetes (future)
- Horizontal pod autoscaling
- GPU node pools for AI/video workers
- Managed PostgreSQL (RDS/Cloud SQL)
- Managed Redis (ElastiCache/Memorystore)
- CDN for media assets
```

## 20. Estimated Complexity

| Module | Complexity | Dependencies |
|--------|-----------|--------------|
| Auth System | Medium | DB, JWT |
| Content Studio | High | AI, Storage |
| Video Processing | Very High | FFmpeg, Workers |
| Social Media | High | OAuth, API Rate Limits |
| Analytics | Medium | DB Aggregation |
| AI Integration | Medium | LLM API |
| Affiliate | Medium | External APIs |
| E-Commerce | High | Payment Integration |
| Android App | Medium | Backend API |
| Production Hardening | Medium | DevOps |