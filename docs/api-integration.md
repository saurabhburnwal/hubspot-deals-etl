# 📋 HubSpot Deals ETL - Integration with HubSpot CRM API v3

This document explains the HubSpot CRM API v3 endpoints the **hubspot-deals-etl** service uses to extract deal data from a HubSpot portal, how it authenticates, paginates, respects rate limits and handles errors.

> Generated from the DLT Generator template `docs/INTEGRATION-DOCS.md` and customised for HubSpot Deals.
> Implementation: [`services/hubspot_api_service.py`](../services/hubspot_api_service.py), [`services/data_source.py`](../services/data_source.py).

---

## 📋 Overview

The service reads deals with the CRM **Objects API** list endpoint. One endpoint is enough for a complete extraction; the others are optional helpers.

### ✅ **Required Endpoint (Essential)**
| **API Endpoint**          | **Purpose**                              | **Version** | **Required Scope**         | **Usage**    |
|---------------------------|------------------------------------------|-------------|----------------------------|--------------|
| `GET /crm/v3/objects/deals` | List all deals (cursor-paginated)       | CRM v3      | `crm.objects.deals.read`   | **Required** |

### 🔧 **Optional Endpoints (Advanced Features)**
| **API Endpoint**                    | **Purpose**                                         | **Version** | **Required Scope**        | **Used by the service** |
|-------------------------------------|-----------------------------------------------------|-------------|---------------------------|--------------------------|
| `GET /crm/v3/properties/deals`      | Property metadata (name, label, **type**)           | CRM v3      | `crm.objects.deals.read` ¹ | Yes - drives type conversion; falls back to a static map on 403 |
| `GET /crm/v3/pipelines/deals`       | Pipelines and stage IDs/labels                      | CRM v3      | `crm.objects.deals.read`  | Seed script only |
| `GET /crm/v3/objects/deals/{dealId}`| Single deal                                         | CRM v3      | `crm.objects.deals.read`  | `get_deal()` helper |
| `GET /account-info/v3/details`      | Portal ID, account type, time zone, currency        | v3          | none beyond a valid token | Credential validation endpoint |
| `POST /crm/v3/objects/deals/search` | Filtered search (e.g. modified since)               | CRM v3      | `crm.objects.deals.read`  | Not used (see below) |

¹ HubSpot also accepts `crm.schemas.deals.read` for the properties API. If neither is granted the service logs a warning and uses its built-in type map.

### 🎯 **Recommendation**
**Use the list endpoint for full extraction.** It returns every deal (including those Search cannot see, e.g. archived deals with `archived=true`), has the normal app burst limit, and has no 10,000-result cap. The Search API is limited to **5 requests/second per token**, caps results at 10,000 per query, and never returns archived records, so it is only worth adding later for incremental "modified since" syncs.

---

## 🔐 Authentication Requirements

### **Private App Access Token (Bearer) Authentication**
```http
GET /crm/v3/objects/deals HTTP/1.1
Host: api.hubapi.com
Authorization: Bearer pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Content-Type: application/json
```

- Tokens are created in **Settings → Integrations → Private Apps** (HubSpot now labels these **Legacy apps → Private**). The token starts with `pat-` followed by the data-centre region (`na1`, `na2`, `eu1`, ...).
- Tokens do not expire on a schedule but can be **rotated** in the app settings; a rotated/revoked token returns `401`.
- The service **never** stores the token in configuration. It arrives in each scan request (`config.auth.accessToken`), is **encrypted with Fernet** (PBKDF2-derived key from `CONFIG_PASSWORD`) before being saved with the job, is decrypted only in the worker, and is never logged.

### **Required Permissions**
- **`crm.objects.deals.read`**: list/read deals and their properties. **This is the only scope the extraction needs.**
- `crm.objects.deals.write`: *only* for `scripts/seed_test_deals.py`, which creates the five test deals. Not needed by the service.

---

## 🌐 HubSpot API Endpoints

Base URL: `https://api.hubapi.com` (configurable with `HUBSPOT_API_BASE_URL`).

### 🎯 **PRIMARY ENDPOINT (Required for Basic Deal Extraction)**

### 1. **List Deals** - `/crm/v3/objects/deals` ✅ **REQUIRED**

**Purpose**: Get a paginated list of all deals with the requested properties. **This is all you need for deal extraction.**

**Method**: `GET`

**URL**: `https://api.hubapi.com/crm/v3/objects/deals`

**Query Parameters**:
| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | 10 | Records per page. **Max 100.** The service uses `HUBSPOT_PAGE_SIZE` (default 100) or the scan's `filters.batchSize`. |
| `after` | string | – | Paging cursor from the previous response's `paging.next.after`. Omit for the first page. |
| `properties` | comma-separated string | a small default set | Properties to return. Unknown names are ignored; known properties with no value are returned as `null`. |
| `propertiesWithHistory` | comma-separated string | – | Also return value history. Lowers the maximum page size; not used by the service. |
| `associations` | comma-separated string | – | Object types whose associated IDs to include (e.g. `contacts,companies`). Supported by `get_deals(associations=...)`, off by default. |
| `archived` | boolean | `false` | `true` returns **only** archived (deleted) deals. Mapped from the scan filter `includeArchived`. |

**Request Example**:
```bash
curl -s "https://api.hubapi.com/crm/v3/objects/deals?limit=100&archived=false&properties=dealname,amount,dealstage,pipeline,closedate,dealtype,description,hs_priority" \
  -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN"
```

**Response Example** (page 1 of 2):
```json
{
  "results": [
    {
      "id": "40123456789",
      "properties": {
        "amount": "25000",
        "closedate": "2026-12-23T17:00:00Z",
        "createdate": "2026-11-08T10:00:00.000Z",
        "dealname": "[DLT TEST] Globex - Analytics Add-on",
        "dealstage": "presentationscheduled",
        "dealtype": "existingbusiness",
        "description": "Upsell of the analytics add-on to an existing customer.",
        "hs_lastmodifieddate": "2026-11-08T10:05:00.000Z",
        "hs_object_id": "40123456789",
        "hs_priority": "medium",
        "pipeline": "default"
      },
      "createdAt": "2026-11-08T10:00:00.000Z",
      "updatedAt": "2026-11-08T10:05:00.000Z",
      "archived": false
    }
  ],
  "paging": {
    "next": {
      "after": "40123456790",
      "link": "https://api.hubapi.com/crm/v3/objects/deals?after=40123456790&limit=100"
    }
  }
}
```

**Response structure**:
| Field | Type | Notes |
|---|---|---|
| `results[]` | array | Deals on this page |
| `results[].id` | string | Deal ID (numeric string). Same value as the `hs_object_id` property. |
| `results[].properties` | object | **All values are strings or `null`**, whatever the property type. Numbers (`"25000"`), booleans (`"true"`), datetimes (ISO-8601 UTC) and dates (`YYYY-MM-DD`) all arrive as strings and must be converted. |
| `results[].createdAt` / `updatedAt` | string (ISO-8601) | Record timestamps |
| `results[].archived` | boolean | `true` only when listing with `archived=true` |
| `results[].archivedAt` | string | Present for archived deals |
| `results[].associations` | object | Only when `associations` is requested |
| `paging.next.after` | string | Cursor for the next page. **`paging` is absent on the last page**, which is how the service detects completion. |

**Pagination algorithm used by the service**:
```python
after = None                                  # or checkpoint cursor when resuming
while True:
    page = GET /crm/v3/objects/deals?limit=100&after=<after>&properties=...
    yield transform(page["results"])
    after = page.get("paging", {}).get("next", {}).get("after")
    if not after:
        break                                 # last page -> final checkpoint
    if page_number % HUBSPOT_CHECKPOINT_INTERVAL == 0:
        save_checkpoint(cursor=after, ...)
```

---

## 🔧 **OPTIONAL ENDPOINTS (Advanced Features Only)**

### 2. **Get Deal Properties** - `/crm/v3/properties/deals` 🔧 **OPTIONAL (used)**

**Purpose**: Discover every deal property in the portal, including custom ones, with its data type. The service calls it once per scan to build a `name → type` map for conversions and to expand `filters.properties = ["*"]` into "all properties".

```bash
curl -s "https://api.hubapi.com/crm/v3/properties/deals" -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN"
```
```json
{
  "results": [
    {
      "name": "amount",
      "label": "Amount",
      "type": "number",
      "fieldType": "number",
      "groupName": "dealinformation",
      "hubspotDefined": true,
      "calculated": false
    },
    {
      "name": "dealstage",
      "label": "Deal Stage",
      "type": "enumeration",
      "fieldType": "radio",
      "groupName": "dealinformation",
      "options": [{ "label": "Appointment Scheduled", "value": "appointmentscheduled" }]
    }
  ]
}
```
`type` is one of `string`, `number`, `date`, `datetime`, `bool`, `enumeration`, `phone_number`. Run `python scripts/export_deal_properties.py` to save the full list for a portal to `test-results/deal-properties.json`.

### 3. **Get Deal Pipelines** - `/crm/v3/pipelines/deals` 🔧 **OPTIONAL**

Returns pipelines and stages (`id`, `label`, `displayOrder`, `metadata.probability`, `metadata.isClosed`). Stage IDs in deal records (`dealstage`) are internal IDs, so this endpoint is needed to show stage labels. The seed script uses it to resolve the stage IDs of the portal's default pipeline.

### 4. **Get a Deal** - `/crm/v3/objects/deals/{dealId}` 🔧 **OPTIONAL**

Same parameters as the list endpoint (except paging); returns one deal object. Exposed as `HubSpotAPIService.get_deal()` for spot checks.

### 5. **Account Details** - `/account-info/v3/details` 🔧 **OPTIONAL (used)**

```json
{ "portalId": 12345678, "accountType": "DEVELOPER_TEST", "timeZone": "US/Eastern", "companyCurrency": "USD", "dataHostingLocation": "na1" }
```
Used by `POST /api/scan/validate-credentials` to show which portal a token belongs to.

---

## 🏷️ Deal Properties

All HubSpot-defined deal properties below can be requested with `properties=`. The **core set** (✅) is requested on every scan (`DEFAULT_DEAL_PROPERTIES`) and stored as typed columns; anything else can be added per scan with `filters.properties`, or `["*"]` for everything. The authoritative list for a given portal, including custom properties, comes from `GET /crm/v3/properties/deals`.

### Deal information
| Property | HubSpot type | Core | Description |
|---|---|---|---|
| `dealname` | string | ✅ | Deal name |
| `amount` | number | ✅ | Deal amount in the deal currency |
| `dealstage` | enumeration | ✅ | Stage ID within the pipeline (see stages below) |
| `pipeline` | enumeration | ✅ | Pipeline ID (`default` for the standard Sales Pipeline) |
| `closedate` | datetime | ✅ | Expected or actual close date |
| `createdate` | datetime | ✅ | Creation timestamp |
| `hs_lastmodifieddate` | datetime | ✅ | Last modification timestamp |
| `dealtype` | enumeration | ✅ | `newbusiness` / `existingbusiness` |
| `description` | string | ✅ | Free-text description |
| `hubspot_owner_id` | enumeration | ✅ | Owner (user) ID |
| `hs_priority` | enumeration | ✅ | `low` / `medium` / `high` |
| `deal_currency_code` | enumeration | ✅ | ISO currency code (multi-currency portals) |
| `amount_in_home_currency` | number | ✅ | Amount converted to the company currency |
| `hs_object_id` | number | ✅ | Record ID (same as `id`) |
| `hubspot_team_id` | enumeration | | Owner's team |
| `hs_all_owner_ids` | enumeration | | All owner IDs |
| `hubspot_owner_assigneddate` | datetime | | When the owner was assigned |
| `hs_created_by_user_id` / `hs_updated_by_user_id` | number | | Creating / last updating user |
| `hs_merged_object_ids` | enumeration | | IDs merged into this deal |
| `hs_was_imported` | bool | | Created by an import |

### Forecast and revenue
| Property | HubSpot type | Core | Description |
|---|---|---|---|
| `hs_deal_stage_probability` | number | ✅ | Probability of the current stage (0-1) |
| `hs_forecast_amount` | number | ✅ | amount × forecast probability |
| `hs_forecast_probability` | number | ✅ | Manual forecast probability |
| `hs_manual_forecast_category` | enumeration | | Forecast category |
| `hs_projected_amount` | number | ✅ | amount × stage probability |
| `hs_closed_amount` | number | ✅ | Amount if closed won, else 0 |
| `hs_acv`, `hs_arr`, `hs_mrr`, `hs_tcv` | number | | Annual / annual recurring / monthly recurring / total contract value (from line items) |
| `hs_num_of_associated_line_items` | number | | Line item count |

### Status and timing
| Property | HubSpot type | Core | Description |
|---|---|---|---|
| `hs_is_closed` | bool | ✅ | Deal is in a closed stage |
| `hs_is_closed_won` | bool | ✅ | Deal is closed won |
| `days_to_close` | number | ✅ | Days from create date to close date |
| `closed_won_reason` | string | ✅ | Why the deal was won |
| `closed_lost_reason` | string | ✅ | Why the deal was lost |
| `hs_next_step` | string | ✅ | Next step |
| `hs_date_entered_<stageId>` / `hs_date_exited_<stageId>` | datetime | | Stage entry/exit timestamps (one pair per stage) |
| `hs_time_in_<stageId>` | number | | Milliseconds spent in a stage |

### Activity and source
| Property | HubSpot type | Core | Description |
|---|---|---|---|
| `num_associated_contacts` | number | ✅ | Associated contact count |
| `num_contacted_notes` | number | ✅ | Number of sales activities |
| `num_notes` | number | ✅ | Number of notes/activities logged |
| `notes_last_updated` | datetime | ✅ | Last activity date |
| `notes_last_contacted` | datetime | | Last contacted |
| `notes_next_activity_date` | datetime | | Next scheduled activity |
| `engagements_last_meeting_booked` | datetime | | Last meeting booked |
| `hs_analytics_source` | enumeration | ✅ | Original source |
| `hs_analytics_source_data_1` / `_2` | string | | Original source drill-down |

### Default Sales Pipeline stages (`pipeline = default`)
| Stage ID (`dealstage`) | Label | Probability | Closed |
|---|---|---|---|
| `appointmentscheduled` | Appointment Scheduled | 0.2 | no |
| `qualifiedtobuy` | Qualified To Buy | 0.4 | no |
| `presentationscheduled` | Presentation Scheduled | 0.6 | no |
| `decisionmakerboughtin` | Decision Maker Bought-In | 0.8 | no |
| `contractsent` | Contract Sent | 0.9 | no |
| `closedwon` | Closed Won | 1.0 | won |
| `closedlost` | Closed Lost | 0.0 | lost |

Custom pipelines use numeric stage IDs; resolve labels via `/crm/v3/pipelines/deals`.

---

## 📊 Data Extraction Flow

### 🎯 **SIMPLE FLOW (Implemented - Required Endpoint Only)**

```
POST /api/scan/start ──► job row (pending, token encrypted)
        │
        ▼  worker thread
validate token (GET /crm/v3/objects/deals?limit=1)  ── 401/403 ─► job failed with clear message
        │
GET /crm/v3/properties/deals  (best effort → type map)
        │
loop: GET /crm/v3/objects/deals?limit=100&after=<cursor>&properties=<core+requested>
        │   ├─ cancel/pause check before each page
        │   ├─ transform strings → typed values + ETL metadata
        │   ├─ yield page to dlt
        │   └─ checkpoint every N pages (cursor of next page)
        ▼
dlt merge into <tenant schema>.hubspot_deals on (_tenant_id, id) → ensure indexes → job completed
```

Each deal is flattened into one row: every requested property becomes a column of the right PostgreSQL type, plus `created_at`, `updated_at`, `archived`, `archived_at` and the ETL metadata columns `_tenant_id`, `_scan_id`, `_extracted_at`, `_page_number`, `_source_service`. See [database-schema.md](database-schema.md).

**Type conversion** (all property values arrive as strings):
| HubSpot type | Example raw value | Python / PostgreSQL |
|---|---|---|
| `number` | `"25000.50"` | `Decimal` → `NUMERIC(18,2)` (`BIGINT` for counts/IDs such as `days_to_close`, `num_notes`, `hs_object_id`) |
| `datetime` | `"2026-12-31T17:00:00Z"` or epoch ms `"1700000000000"` | timezone-aware `datetime` → `TIMESTAMPTZ` |
| `date` | `"2026-12-31"` | `date` → `DATE` |
| `bool` | `"true"` / `"false"` | `bool` → `BOOLEAN` |
| `enumeration`, `string`, `phone_number` | `"closedwon"` | `str` → `VARCHAR` |
| any | `""` or `null` | `NULL` |

### 🔧 **ADVANCED FLOW (Optional - Not Implemented)**
1. **Associations**: pass `associations=contacts,companies` on the list call (supported by `get_deals`) to load deal ↔ contact/company links into a child table.
2. **Stage labels**: cache `/crm/v3/pipelines/deals` per tenant and join on `dealstage`.
3. **Incremental sync**: `POST /crm/v3/objects/deals/search` with a filter `hs_lastmodifieddate GTE <last_successful_run>` and sort ascending, while staying under 5 req/s and the 10,000-result limit per query.
4. **Property history**: `propertiesWithHistory=dealstage,amount` for stage-change analytics (smaller pages).

---

## ⚡ Performance Considerations

### **Rate Limiting**

HubSpot limits private apps per app over a rolling **10-second window**, plus a **daily** limit per account:

| HubSpot tier | Burst (per 10 s, per app) | Daily (per account, shared by all apps) |
|---|---|---|
| Free / Starter | 100 | 250,000 |
| Professional | 190 | 625,000 |
| Enterprise | 190 | 1,000,000 |
| API Limit Increase add-on | 250 | +1,000,000 per pack (max 2) |
| Search API | 5 requests / second per token | counts toward daily |

The assessment specifies **150 requests / 10 seconds**, which is the service default (`HUBSPOT_RATE_LIMIT_REQUESTS=150`, `HUBSPOT_RATE_LIMIT_WINDOW_SECONDS=10`). Set it to 100 for Free/Starter portals. Developer test accounts follow their own (Free-like) limits.

The service uses three layers:
1. **Client-side sliding window** (`SlidingWindowRateLimiter`): blocks before a request would exceed N requests per window. Thread-safe.
2. **Header-driven adaptive throttle**: every response's `X-HubSpot-RateLimit-Remaining` / `-Max` / `-Interval-Milliseconds` / `-Daily` / `-Daily-Remaining` headers are captured. When ≤ 5 requests remain in the window the client pauses for half a window, which protects against other apps sharing the portal's quota.
3. **429 retry**: on `429 Too Many Requests` the client honours `Retry-After` if present, otherwise waits out the window, and retries up to `HUBSPOT_MAX_RETRIES` (default 3).

Full extraction cost: `ceil(deals / 100)` list calls + 1 validation call + 1 properties call. 10,000 deals ≈ 102 requests, well under one 10-second burst at 150/10s with throttling.

HubSpot also asks that **error responses stay under 5 % of daily requests**. Failing fast on 401/403 (no retries) keeps the service within that.

### **Batch Processing**
- Page size 100 (the API maximum) minimises requests.
- Each page is yielded to dlt as a list, so the extract step buffers whole pages.
- Requesting only the needed properties keeps payloads small; `["*"]` (200+ properties) roughly triples the response size.

### **Error Handling**

HubSpot error body:
```json
{
  "status": "error",
  "message": "Authentication credentials not found. This API supports OAuth 2.0 authentication...",
  "correlationId": "a43683b0-5717-4ceb-80b4-104d02915d8c",
  "category": "INVALID_AUTHENTICATION"
}
```

| Status | `category` | Meaning | Service behaviour |
|---|---|---|---|
| 400 | `VALIDATION_ERROR` | Bad parameter (e.g. `limit` > 100) | `HubSpotValidationError`, no retry |
| 401 | `INVALID_AUTHENTICATION` | Token missing, malformed, rotated or revoked | `HubSpotAuthenticationError`, no retry, scan fails with "HubSpot authentication failed" |
| 403 | `MISSING_SCOPES` | Token lacks `crm.objects.deals.read` | `HubSpotPermissionError`, no retry, scan fails with a scope message |
| 404 | `OBJECT_NOT_FOUND` | Unknown deal ID / path | `HubSpotNotFoundError` |
| 429 | `RATE_LIMITS` (`policyName`: `TEN_SECONDLY_ROLLING` or `DAILY`) | Burst or daily limit hit | Retry with `Retry-After` / window back-off, then `HubSpotRateLimitError` |
| 500/502/503/504 | – | HubSpot-side failure | Exponential back-off (1 s, 2 s, 4 s), then `HubSpotServerError` |
| network | – | Timeout / connection reset | Same back-off as 5xx |

Every error log includes `status_code`, `category` and HubSpot's `correlationId`, the ID HubSpot support asks for. When a page fails after retries, an `main_data_error` checkpoint is saved and the job is marked `failed` with the message.

---

## 🔒 Security Requirements

### **API Token Permissions**

#### ✅ **Required (Minimum Permissions)**
- `crm.objects.deals.read`

#### 🔧 **Optional (Advanced Features)**
- `crm.schemas.deals.read`: property metadata, if the read scope alone is refused in a portal
- `crm.objects.contacts.read`, `crm.objects.companies.read`: associations
- `crm.objects.deals.write`: **seed script only**; do not grant it to the production extraction token

### **User Permissions**

#### ✅ **Required (Minimum)**
- A **Super Admin** (or a user with *App Marketplace / Private app* access) to create the private app and copy the token.

#### 🔧 **Optional (Advanced Features)**
- Access to all pipelines/teams if deals are restricted by team permissions. Private app tokens see all records the scopes allow.

### Token handling in this service
- Not in `.env`, `docker-compose.yml` or logs; sent per request and stored **encrypted** in `jobs.config.auth`.
- `.env` and other secrets files are git-ignored; only `.env.example` (placeholders) is committed.
- Rotate the token in HubSpot if it is ever exposed; old tokens immediately return 401.

---

## 📈 Monitoring & Debugging

### **Request Headers for Debugging**
```http
Authorization: Bearer pat-na1-...
Accept: application/json
User-Agent: hubspot-deals-etl/1.0
```

### **Response Validation**
- Check `results` is a list and every item has `id` and `properties`.
- Completion is "no `paging.next.after`", not an empty page.
- Rate-limit headers on every response:
  ```http
  X-HubSpot-RateLimit-Max: 150
  X-HubSpot-RateLimit-Remaining: 149
  X-HubSpot-RateLimit-Interval-Milliseconds: 10000
  X-HubSpot-RateLimit-Daily: 250000
  X-HubSpot-RateLimit-Daily-Remaining: 249873
  ```

### **API Usage Metrics**
- `HubSpotAPIService.get_api_usage()` returns the last rate-limit headers plus `requests_made`. It is stored in the final checkpoint's `checkpoint_data.api_usage` and returned by `POST /api/scan/validate-credentials`.
- Each call is logged via `log_api_call` with method, status code and duration (ms).
- HubSpot's own view: *Settings → Integrations → Private Apps → [app] → Logs*.

---

## 🧪 Testing API Integration

### **Test Authentication**
```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://api.hubapi.com/crm/v3/objects/deals?limit=1" \
  -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN"        # 200 = valid with deals scope

# or through the service
curl -s -X POST http://localhost:5200/api/scan/validate-credentials \
  -H "Content-Type: application/json" -d "{\"accessToken\":\"$HUBSPOT_ACCESS_TOKEN\"}"
```

### **Test Deal Listing**
```bash
curl -s "https://api.hubapi.com/crm/v3/objects/deals?limit=5&properties=dealname,amount,dealstage,closedate" \
  -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" | python -m json.tool
```

### **Test Deal Details**
```bash
curl -s "https://api.hubapi.com/crm/v3/objects/deals/<DEAL_ID>?properties=dealname,amount,dealstage" \
  -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN"
```

### **Automated tests**
- `tests/test_hubspot_deals.py`: 12 unit tests against `tests/mock_hubspot.py` (a stdlib mock of these endpoints) covering pagination, `limit` capping, 401/403 mapping, 429 retry with `Retry-After`, the sliding-window limiter, type conversion, checkpointing and lossless pause/resume.
- `scripts/e2e_test.py`: end-to-end run against the live service (real HubSpot or the mock).

---

## 🚨 Common Issues & Solutions

### **Issue**: 401 Unauthorized
Token copied incompletely, rotated, or the private app deleted. Re-copy it from the private app's *Auth* tab. Make sure the header is `Authorization: Bearer <token>`, not `hapikey=` (API keys were retired in 2022).

### **Issue**: 403 Forbidden (`MISSING_SCOPES`)
Edit the private app → *Scopes* → add `crm.objects.deals.read` → *Commit changes*. The token stays the same.

### **Issue**: 429 Rate Limited
Another integration may be sharing the portal quota, or the limit is set above the tier. Lower `HUBSPOT_RATE_LIMIT_REQUESTS` (100 for Free/Starter). The response's `policyName` says whether it was the 10-second (`TEN_SECONDLY_ROLLING`) or the `DAILY` limit; daily limits reset at midnight in the portal's time zone.

### **Issue**: Empty Deal List
Deals exist in a different portal (check `portalId` from `validate-credentials`), or you listed with `archived=true`. A newly created deal is visible immediately in the list endpoint (Search can lag by a few seconds).

### **Issue**: Property comes back `null`
The deal has no value, or the property name is misspelled (unknown names are silently dropped). Check names with `/crm/v3/properties/deals`.

### **Issue**: Need Associations/Stage Labels But Want to Keep It Simple
Keep the core extraction as is and add a second dlt resource, using the optional endpoints above.

---

## 💡 **Implementation Recommendations**

### 🎯 **Phase 1: Start Simple (Implemented)**
List endpoint + properties metadata, typed columns, merge on `(_tenant_id, id)`, checkpoints, and rate limiting.

### 🔧 **Phase 2: Add Advanced Features (If Needed)**
Associations, pipeline/stage dimension tables, incremental sync via Search on `hs_lastmodifieddate`, and property history.

### ⚡ **Performance Tip**
Request only the properties you need, keep `limit=100`, and run scans for different tenants in parallel. The burst limit is **per app**, so each tenant's private app has its own budget.

---

## 📞 Support Resources
- CRM deals API guide: https://developers.hubspot.com/docs/api-reference/legacy/crm/objects/deals/guide
- Using object APIs (paging, properties): https://developers.hubspot.com/docs/guides/crm/using-object-apis
- API usage guidelines and limits: https://developers.hubspot.com/docs/developer-tooling/platform/usage-guidelines
- Private apps: https://developers.hubspot.com/docs/apps/legacy-apps/private-apps/overview
- CRM Search API: https://developers.hubspot.com/docs/api-reference/search/guide
