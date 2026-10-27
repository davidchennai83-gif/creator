# Tamil Budget Finds Autopilot

The Autopilot is the **control plane** for the daily affiliate pipeline. It does
not replace the existing scheduler or uploaders. It refills the catalogue,
chooses the product, records every stage, watches the real video job and uploader
logs, and retries a missing Instagram/Facebook post.

```
06:00  feed sync (optional, once a day)
18:00  Autopilot selects + pins the product
19:00  existing scheduler renders the video
19:30  YouTube upload schedule
19:45  Facebook upload schedule
20:00  Instagram upload schedule
+20m   Autopilot retries only the platforms that are still missing
+      Autopilot reconciles logs and tracks clicks / orders / commission
```

## What is real (and what is not)

- The Autopilot **does not create clicks, orders, views or engagement**.
- A **SAMPLE** product has no commission link. It is labelled
  `SAMPLE / NO COMMISSION` in the admin and `Sample product` in the caption.
- A real affiliate link is required for commission tracking. Supported shops:
  **Meesho, Amazon, Flipkart, Myntra, AJIO, Tata CLiQ, Snapdeal** and the
  link-conversion networks **EarnKaro, Cuelinks, INRDeals, vCommission,
  Admitad, Impact, Optimise**.
- A plain product URL is *not* treated as an affiliate link. It must carry a
  tracking token (`aff_id`, `tag`, `affid`...), come from a wrapper network, or
  be explicitly marked verified on import.
- YouTube verification is never bypassed. If the channel hits the daily upload
  limit, the uploader records the reason and the video stays pending.

## Zero-touch setup (one time)

1. Log in as the owner and open **Meesho Finds → Autopilot**.
2. Add a **product feed**. Either:
   - paste a CSV / link-list URL (Google Sheets **Publish to web → CSV**, an
     affiliate-network export, or a small static CSV), or
   - drop CSV/TXT files into `backend/storage/finds/feed/`, or
   - set a local file/folder path in **Product feed**.
3. Press **Save & sync now**. The importer is idempotent: unchanged content is
   skipped, products are upserted by external id.
4. Turn on **Full autonomy** (`auto_mode`). This sets:
   - `auto_prepare=true` — pick before the 19:00 render,
   - `approval_required=false` — no approval click,
   - `auto_publish=true` — retry missing IG/FB posts after the grace window.
5. Recommended: turn on **Block demo links from publishing**
   (`require_affiliate_link=true`) once the feed contains real affiliate links.
   The Autopilot then replaces a sample pin with a commission-ready product
   before the render.

After this, the normal daily loop needs no clicks:

```
feed -> auto-pick -> 19:00 render -> 19:30/19:45/20:00 schedules -> retry -> track
```

## Feed formats

The importer accepts two shapes.

**CSV** (headers are normalised; only `title` and `affiliate_url` are required):

```csv
external_id,title,title_ta,category,price,mrp,rating,orders_count,commission_percent,affiliate_url,image_url,features,cautions,demo,affiliate_verified
a1,Steel Bottle,ஸ்டீல் பாட்டில்,Home,299,699,4.4,18600,8,https://www.meesho.com/...?...aff_id=...,,Leak-proof|1 litre,Hand wash,false,false
```

Separate features/cautions with `|`. If `demo` is omitted, the importer infers
it from the link: a tracked/wrapper link is real, a plain/search URL is SAMPLE.

**Link list** (one per line):

```
Title | https://www.amazon.in/dp/...?...tag=yourtag | 499 | 1299 | Home | 4
https://earnkaro.com/...
```

## Supported affiliate platforms

| Platform | Link type | Notes |
| --- | --- | --- |
| Meesho | marketplace | Current budget catalogue; affiliate CSV export. |
| Amazon Associates | marketplace | Needs the `tag=` parameter. PA-API access is separate. |
| Flipkart Affiliate | marketplace | Needs `affid=` or a network wrapper. |
| Myntra / AJIO / Tata CLiQ / Snapdeal | marketplace | Usually via a network wrapper. |
| EarnKaro | wrapper | Converts a normal shop URL; no public API for link creation. |
| Cuelinks | wrapper | One dashboard for many brands; deeplink API on approval. |
| INRDeals | wrapper | Coupons + deeplinks; API on approval. |
| vCommission / Admitad / Impact / Optimise | wrapper | Brand/network approvals; good for fashion and electronics. |

The most automation-friendly path is a network that gives you either a product
feed URL or a deeplink API. Meesho/Amazon/Flipkart do not expose link creation
without an approved affiliate account, so the owner still has to create that
account and supply the feed/link once.

## Daily use

- Open **Meesho Finds → Autopilot** at any time to see the current run.
- **Pipeline** shows Discover → Score → Approve → Script → Render → YouTube →
  Facebook → Instagram → Track.
- **Post now** is only a manual override. Normal operation does not need it.
- **Run pass** reconciles immediately instead of waiting for the 15-minute tick.
- **Pin** on a candidate selects that product for the date in the **Day** field.
  Pinning cannot change a video that was already rendered.
- **Sync feed** imports new rows immediately; the 06:00 tick does it otherwise.

## Configuration

Stored in `backend/storage/finds/agent_config.json`:

| Key | Default | Meaning |
| --- | --- | --- |
| `enabled` | `true` | Run the background tick. |
| `auto_mode` | `false` | One switch for select + no approval + publish retries. |
| `auto_prepare` | `true` | Select + pin a product at `prepare_at`. |
| `prepare_at` | `18:00` | IST selection time. |
| `approval_required` | `false` | Wait for owner approval before the render. |
| `require_affiliate_link` | `false` | Block publishing for sample/search products. |
| `auto_publish` | `false` | Retry missing platforms after the grace window. |
| `auto_publish_platforms` | `instagram, facebook` | Platforms the retry layer may post. |
| `publish_grace_minutes` | `20` | Wait for the normal schedule before retrying. |
| `max_publish_attempts` | `2` | Real attempts per platform per day. |
| `feed_url` | `""` | CSV/link-list URL, fetched daily. |
| `feed_path` | `""` | Optional local file/folder; defaults to `storage/finds/feed`. |
| `feed_sync_at` | `06:00` | IST feed sync time. |
| `platforms` | all three | Platforms tracked by the run. |

## API

All routes require an authenticated editor/admin:

```
GET  /api/v1/finds/admin/agent/status?day=YYYY-MM-DD
GET  /api/v1/finds/admin/agent/runs
GET  /api/v1/finds/admin/agent/events
POST /api/v1/finds/admin/agent/prepare     {day, force, product_id}
POST /api/v1/finds/admin/agent/approve     {run_id, approved}
POST /api/v1/finds/admin/agent/publish     {run_id, platform, force}
POST /api/v1/finds/admin/agent/links       {links, real, category}
POST /api/v1/finds/admin/agent/config      {enabled, auto_mode, feed_url, ...}
POST /api/v1/finds/admin/agent/feed/sync
POST /api/v1/finds/admin/agent/tick
```

## Files

- `backend/app/finds_agent.py` — selection, run store, feed sync, reconcile,
  publish, link importer and status payload.
- `backend/app/affiliate.py` — network detection and commission-link checks.
- `backend/app/finds.py` — product catalogue, `day_picks`, `today_pick`,
  clicks/orders/analytics.
- `backend/app/api/routes/finds.py` — Autopilot API routes.
- `frontend/src/pages/FindsAdmin.tsx` — Autopilot tab.
- `backend/app/voice/agent.py` — calls `finds_agent.tick()` every loop.

## Troubleshooting

- **"No active products"** — connect a feed or import the affiliate CSV.
- **"Zero-touch mode has no product feed yet"** — add a feed URL or drop a CSV
  into `storage/finds/feed`.
- **"Sample product"** — add the real affiliate link and commission %; turn on
  **Block demo links from publishing** once the catalogue is ready.
- **Feed returns HTML** — in Google Sheets use **File → Share → Publish to web**
  and pick CSV, not the normal edit URL.
- **"Today's video already exists"** — the 19:00 render already used a product;
  choose a future date to change the pick.
- **Platform "due but not posted"** — check the uploader run and the platform
  session (CreatorRecorder for YouTube, CreatorSocial for Instagram/Facebook).
- **YouTube daily limit** — complete the one-time verification in YouTube Studio
  or wait 24 hours. The Autopilot cannot bypass this.
