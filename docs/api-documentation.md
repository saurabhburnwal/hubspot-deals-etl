# HubSpot Deals ETL - API Documentation

REST API exposed by the **hubspot-deals-etl** service: start HubSpot deal extraction scans, monitor and control them (pause / resume / cancel), and read the extracted deals.

> Generated from the DLT Generator template `docs/APi-DOCS.md` and customised for HubSpot Deals. Response bodies below were captured from a running instance.
> Interactive docs: **`/docs/`** (Swagger UI) · machine-readable spec: **`/api/swagger.json`**.

## 📋 Table of Contents
1. [Overview](#-overview)
2. [Authentication](#-authentication)
3. [Base URLs](#-base-urls)
4. [Common Response Formats](#-common-response-formats)
5. [Scan Endpoints](#-scan-endpoints)
6. [Results Endpoints](#-results-endpoints)
7. [Pipeline & Maintenance Endpoints](#-pipeline--maintenance-endpoints)
8. [Health & Stats Endpoints](#-health--stats-endpoints)
9. [Error Handling](#-error-handling)
10. [Examples](#-examples)

---

## 🔍 Overview

### API Version
- **Version**: 1.0.0
- **Prefix**: `/api` (the generator README says `/api/v1`, but the generated code mounts everything at `/api`)
- **Format**: JSON request and response bodies (`Content-Type: application/json`)

### Key Features
- Asynchronous scans: `POST /api/scan/start` returns `202` immediately and extraction runs in a background worker.
- Cursor-based HubSpot pagination with checkpoints, plus **pause / resume / cancel**.
- Per-tenant data isolation (`organizationId` → Postgres schema `hubspot_deals_<org>`).
- Credential pre-check endpoint, so a bad token fails before a scan is created.
- Access tokens are encrypted at rest and never returned in plaintext.

### Endpoint summary
| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/scan/validate-credentials` | Check a HubSpot token and scope |
| `POST` | `/api/scan/start` | Start a deals extraction scan |
| `GET` | `/api/scan/{scanId}/status` | Scan status, progress and checkpoint |
| `POST` | `/api/scan/{scanId}/pause` | Pause a running scan |
| `POST` | `/api/scan/{scanId}/resume` | Resume a paused or crashed scan |
| `POST` | `/api/scan/{scanId}/cancel` | Cancel a scan |
| `DELETE` | `/api/scan/{scanId}/remove` | Delete a scan and the rows it wrote |
| `GET` | `/api/scan/list` | List scans (filter by tenant, paginated) |
| `GET` | `/api/scan/statistics` | Scan counts by status |
| `GET` | `/api/results/{scanId}/tables` | Tables produced by a completed scan |
| `GET` | `/api/results/{scanId}/result` | Paginated extracted deals |
| `GET` | `/api/pipeline/info` | DLT pipeline configuration |
| `POST` | `/api/maintenance/cleanup` | Delete old scan records |
| `POST` | `/api/maintenance/detect-crashed` | Mark stale running scans as crashed |
| `GET` | `/health` | Liveness/readiness (database) |
| `GET` | `/api/health` | Health plus pipeline details |
| `GET` | `/api/stats` | Service statistics |
| `GET` | `/docs/` | Swagger UI |

---

## 🔐 Authentication

There are two separate credentials.

### 1. Service API key (inbound, optional)
| Setting | Behaviour |
|---|---|
| `SERVICE_API_KEY` unset (default in dev) | No inbound authentication. Run only on a trusted network. |
| `SERVICE_API_KEY=<secret>` | Every `/api/*` call must send `X-API-Key: <secret>`, except `/api/health` and `/api/swagger.json`. Missing or wrong key → `401`. `/health` and `/docs/` stay open. Compared in constant time. |

In Swagger UI, click **Authorize** and paste the key.

### 2. HubSpot access token (outbound, required per scan)

#### Required Credentials
A HubSpot **private app access token** (`pat-na1-...`), sent in the scan request body as `config.auth.accessToken`. The service does **not** read the token from environment variables, so each tenant brings its own token.

#### Required Permissions
The private app needs scope **`crm.objects.deals.read`**. Without it, `validate-credentials` returns `403` and scans fail with `"HubSpot token is missing the crm.objects.deals.read scope"`.

#### Authentication Headers
```http
POST /api/scan/start HTTP/1.1
Content-Type: application/json
X-API-Key: <SERVICE_API_KEY>            # only if enabled
```
The HubSpot token travels in the body, never in a header or query string, so it does not appear in access logs. It is encrypted (Fernet, key derived from `CONFIG_PASSWORD`) before being written to the `jobs` table, and status responses only ever show the encrypted blob.

---

## 🌐 Base URLs

### Development
```
http://localhost:5200
```

### Staging
```
http://localhost:5201        # docker compose --profile stage up
```

### Production
```
http://localhost:5202        # docker compose --profile prod up (behind TLS-terminating gateway)
```

### Swagger Documentation
```
http://localhost:5200/docs/             # Swagger UI
http://localhost:5200/api/swagger.json  # OpenAPI 2.0 spec
```

---

## 📊 Common Response Formats

### Success Response
```json
{
  "success": true,
  "data": { }
}
```
Action endpoints may return `message` instead of, or in addition to, `data`.

### Error Response (Validation)
`400` with a per-field breakdown:
```json
{
  "success": false,
  "message": "Configuration validation failed: {...}",
  "error": "Configuration validation failed: {...}",
  "validation_errors": {
    "config": {
      "scanId": ["Scan ID can only contain letters, numbers, underscores, and hyphens"],
      "type": { "0": ["Must be one of: deals."] },
      "auth": { "accessToken": ["Shorter than minimum length 10."] }
    }
  }
}
```

### Error Response (Application Logic)
```json
{
  "success": false,
  "message": "Cannot pause job with status: completed. Only running or pending jobs can be paused.",
  "error": "Cannot pause job with status: completed. Only running or pending jobs can be paused."
}
```

### Pagination Response
```json
"pagination": {
  "total": 5,
  "limit": 100,
  "offset": 0,
  "hasMore": false,
  "totalPages": 1
}
```

---

## 🔍 Scan Endpoints

### 1. Validate Credentials

**Endpoint**: `POST /api/scan/validate-credentials`

Checks that a HubSpot token works and has the deals scope. It makes one `GET /crm/v3/objects/deals?limit=1` call plus `GET /account-info/v3/details`, and does not create a scan.

#### Request Body
```json
{ "accessToken": "pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" }
```

#### Response (200)
```json
{
  "success": true,
  "message": "Credentials valid",
  "data": {
    "valid": true,
    "has_deals_scope": true,
    "error": null,
    "portalId": 12345678,
    "accountType": "DEVELOPER_TEST",
    "timeZone": "US/Eastern",
    "companyCurrency": "USD",
    "rateLimit": {
      "daily_limit": 250000,
      "daily_remaining": 249000,
      "interval_ms": 10000,
      "interval_max": 150,
      "interval_remaining": 149,
      "captured_at": "2026-11-08T13:33:25.520294+00:00",
      "requests_made": 2
    }
  }
}
```

#### Status Codes
| Code | Meaning |
|---|---|
| 200 | Token valid with `crm.objects.deals.read` |
| 400 | `accessToken` missing |
| 401 | Token invalid / revoked (`data.error` has HubSpot's message and correlationId) |
| 403 | Token valid but missing the deals scope |

---

### 2. Start Extraction

**Endpoint**: `POST /api/scan/start`

Creates the scan record synchronously (so duplicate IDs are rejected reliably), then extracts in the background.

#### Request Body
```json
{
  "config": {
    "scanId": "hubspot-deals-scan-001",
    "organizationId": "acme-corp",
    "type": ["deals"],
    "auth": {
      "accessToken": "pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    },
    "filters": {
      "properties": ["hs_acv", "hs_arr"],
      "includeArchived": false,
      "batchSize": 100,
      "dateRange": { "startDate": "2026-01-01", "endDate": "2026-12-31" }
    }
  }
}
```

#### Parameters
| Field | Type | Required | Rules | Description |
|---|---|---|---|---|
| `config.scanId` | string | ✅ | 1-255 chars, `[A-Za-z0-9_-]`, unique | Client-chosen scan ID |
| `config.organizationId` | string | ✅ | 1-255 chars | Tenant ID. Data goes to schema `hubspot_deals_<org>` |
| `config.type` | string[] | ✅ | must be `["deals"]` | Scan type |
| `config.auth.accessToken` | string | ✅ | ≥ 10 chars | HubSpot private app token |
| `config.filters.properties` | string[] | | non-empty if given | Extra deal properties on top of the 30 core ones, or `["*"]` for every property in the portal |
| `config.filters.includeArchived` | boolean | | default `false` | `true` extracts **archived** deals (HubSpot `archived=true`) |
| `config.filters.batchSize` | integer | | 1-100 | HubSpot page size (default `HUBSPOT_PAGE_SIZE` = 100) |
| `config.filters.dateRange.startDate` / `endDate` | string | | `YYYY-MM-DD`, start ≤ end | Keep only deals whose `createdate` falls in the range (inclusive). Applied client-side. |

#### Response (202)
```json
{
  "success": true,
  "message": "Scan initialization accepted and is now processing in the background."
}
```

#### Status Codes
| Code | Meaning |
|---|---|
| 202 | Accepted; poll the status endpoint |
| 400 | No body / validation failed |
| 401 | Service API key missing or invalid (when enabled) |
| 409 | `scanId` already exists |
| 500 | Unexpected server error |

Token problems surface asynchronously: the scan moves to `failed` with `errorMessage` such as `HubSpot authentication failed: Authentication credentials not found. | status=401 | category=INVALID_AUTHENTICATION | correlationId=...`. Call `validate-credentials` first to catch them synchronously.

---

### 3. Get Extraction Status

**Endpoint**: `GET /api/scan/{scanId}/status`

#### Path Parameters
| Name | Description |
|---|---|
| `scanId` | Scan ID used at start |

#### Response (Existing Extraction)
```json
{
  "success": true,
  "data": {
    "scanId": "hubspot-deals-scan-001",
    "organizationId": "acme-corp",
    "type": "deals",
    "status": "completed",
    "startTime": "2026-11-08T13:33:34.732023+00:00",
    "endTime": "2026-11-08T13:33:40.487943+00:00",
    "lastHeartbeat": "2026-11-08T13:33:40.061844+00:00",
    "recordsExtracted": 5,
    "errorMessage": null,
    "config": {
      "auth": "Z0FBQUFBQnE4SG91bFJfb0JJ...<encrypted>",
      "filters": { "includeArchived": false, "batchSize": 2 },
      "type": ["deals"]
    },
    "metadata": {
      "pipeline_name": "hubspot_deals_extraction",
      "destination": "postgres",
      "dataset_name": "hubspot_deals_acme_corp",
      "source_type": "hubspot_deals",
      "extraction_summary": { "total_records": 5 },
      "table_record_counts": { "hubspot_deals": 5 },
      "completed_at": "2026-11-08T13:33:40.481005+00:00"
    },
    "duration": 5.75592,
    "checkpointInfo": {
      "latestCheckpoint": {
        "id": 3,
        "job_id": "hubspot-deals-scan-001",
        "createdAt": "2026-11-08T13:33:40.056402+00:00",
        "phase": "main_data_completed",
        "recordsProcessed": 5,
        "cursor": null,
        "pageNumber": 3,
        "batchSize": 2,
        "checkpoint_data": {
          "service": "hubspot_deals",
          "tenant_id": "acme-corp",
          "completion_status": "success",
          "total_pages": 3,
          "api_usage": { "interval_max": 150, "interval_remaining": 149, "requests_made": 5 }
        }
      },
      "lastCheckpointAt": "2026-11-08T13:33:40.056402+00:00"
    }
  }
}
```

#### Response (Non-existent Extraction)
```json
{
  "success": false,
  "message": "No scan found with ID: nope",
  "error": "No scan found with ID: nope"
}
```

#### Status Values
| Status | Meaning | Allowed actions |
|---|---|---|
| `pending` | Registered, worker starting | pause, cancel |
| `running` | Extracting pages | pause, cancel |
| `paused` | Stopped at a page boundary; rows so far are loaded | resume, cancel |
| `resuming` | Resume accepted, worker restarting | – |
| `completed` | All pages loaded | remove, read results |
| `failed` | Error (see `errorMessage`) | remove |
| `cancelled` | Stopped by user; rows so far are loaded | remove |
| `crashed` | Detected by `detect-crashed` (stale heartbeat) | resume |

#### Checkpoint phases
`main_data` (every `HUBSPOT_CHECKPOINT_INTERVAL` pages), `main_data_paused`, `main_data_cancelled`, `main_data_error`, `main_data_completed`. `cursor` is the HubSpot `after` value of the next page.

#### Status Codes
| Code | Meaning |
|---|---|
| 200 | Found |
| 404 | Unknown `scanId` |

---

### 4. Pause Extraction

**Endpoint**: `POST /api/scan/{scanId}/pause`

Requests a pause. The extractor checks between pages, saves a `main_data_paused` checkpoint with the next cursor, and exits; dlt loads everything extracted so far.

#### Response (200)
```json
{
  "success": true,
  "scanId": "hubspot-deals-scan-001",
  "message": "Job hubspot-deals-scan-001 has been paused successfully",
  "data": {
    "scanId": "hubspot-deals-scan-001",
    "previousStatus": "running",
    "currentStatus": "paused",
    "pausedAt": "2026-11-08T13:35:34.802000+00:00",
    "progress": { "recordsProcessed": 1, "currentPage": 1, "phase": "main_data", "progressPercentage": null }
  }
}
```

#### Status Codes
| Code | Meaning |
|---|---|
| 200 | Paused |
| 400 | Not `running`/`pending` (e.g. `"Cannot pause job with status: completed. Only running or pending jobs can be paused."`) |
| 404 | Unknown `scanId` |

---

### 5. Resume Extraction

**Endpoint**: `POST /api/scan/{scanId}/resume`

Resumes a `paused` or `crashed` scan in the background.
- From a **pause** checkpoint, it continues at the saved cursor (lossless, no re-reading).
- From a **crash**, it restarts from page 1. Rows extracted after the last load may not have been committed, and the merge key `(_tenant_id, id)` makes the re-read idempotent.

#### Response (202)
```json
{
  "success": true,
  "scanId": "hubspot-deals-scan-001",
  "message": "Job hubspot-deals-scan-001 is resuming from checkpoint",
  "data": {
    "scanId": "hubspot-deals-scan-001",
    "previousStatus": "paused",
    "currentStatus": "resuming",
    "resumedAt": "2026-11-08T13:35:37.120000+00:00",
    "resumePoint": { "page": 2, "recordsProcessed": 2, "phase": "main_data_paused", "cursor": "2" }
  }
}
```

#### Status Codes
| Code | Meaning |
|---|---|
| 202 | Resuming |
| 400 | Not resumable (`"Cannot resume job with status: completed. Only paused or crashed jobs can be resumed."`) or no checkpoint |
| 404 | Unknown `scanId` |

---

### 6. Cancel Extraction

**Endpoint**: `POST /api/scan/{scanId}/cancel`

#### Response (200)
```json
{ "success": true, "scanId": "hubspot-deals-scan-001", "status": "cancelled", "message": "Job cancelled successfully" }
```

#### Status Codes
| Code | Meaning |
|---|---|
| 200 | Cancelled (rows already extracted are kept) |
| 400 | Already finished (`"Cannot cancel job with status: completed"`) |
| 404 | Unknown `scanId` |

---

### 7. Remove Extraction

**Endpoint**: `DELETE /api/scan/{scanId}/remove`

Deletes the scan record, its checkpoints, and the deal rows whose `_scan_id` is this scan. Running scans must be cancelled first.

#### Response (200)
```json
{
  "success": true,
  "message": "Scan hubspot-deals-scan-001 successfully removed",
  "data": { "scanId": "hubspot-deals-scan-001", "tablesRemoved": 5, "metadataRemoved": true }
}
```

#### Status Codes
| Code | Meaning |
|---|---|
| 200 | Removed |
| 400 | Scan still `running`/`pending` |
| 404 | Unknown `scanId` |

---

### 8. List Scans

**Endpoint**: `GET /api/scan/list`

#### Query Parameters
| Name | Default | Description |
|---|---|---|
| `organizationId` | – | Filter by tenant |
| `limit` | 20 | Max 100 |
| `offset` | 0 | |

#### Response (200)
```json
{
  "success": true,
  "data": {
    "scans": [
      { "scanId": "hubspot-deals-scan-001", "organizationId": "acme-corp", "type": "deals", "status": "completed",
        "recordsExtracted": 5, "startTime": "...", "endTime": "...", "duration": 11.94, "metadata": { } }
    ],
    "pagination": { "total": 1, "limit": 20, "offset": 0, "hasMore": false, "returned": 1 }
  }
}
```

### 9. Scan Statistics

**Endpoint**: `GET /api/scan/statistics?organizationId=acme-corp`

```json
{
  "success": true,
  "data": {
    "total_jobs": 4,
    "status_breakdown": { "pending": 0, "running": 0, "completed": 4, "paused": 0, "failed": 0, "cancelled": 0, "crashed": 0, "resuming": 0 },
    "recent_jobs_7_days": 4,
    "total_records_extracted": 20,
    "organization_filter": "acme-corp",
    "generated_at": "2026-11-08T13:42:21.300586+00:00"
  }
}
```

---

## 📦 Results Endpoints

### 1. Get Result Tables

**Endpoint**: `GET /api/results/{scanId}/tables` (completed scans only)

```json
{
  "success": true,
  "data": {
    "scanId": "hubspot-deals-scan-001",
    "datasetName": "hubspot_deals_acme_corp",
    "tables": [ { "name": "hubspot_deals", "rowCount": 5, "extractedCount": 5 } ],
    "totalTables": 1
  }
}
```

### 2. Get Extraction Results

**Endpoint**: `GET /api/results/{scanId}/result`

Returns deals from the tenant's `hubspot_deals` table, newest extraction first. Column definitions are in [database-schema.md](database-schema.md).

#### Path Parameters
| Name | Description |
|---|---|
| `scanId` | A **completed** scan |

#### Query Parameters
| Name | Default | Description |
|---|---|---|
| `tableName` | `hubspot_deals` | Table to read |
| `limit` | 100 | Max 500 |
| `offset` | 0 | |

#### Response (200)
```json
{
  "success": true,
  "data": {
    "tableName": "hubspot_deals",
    "records": [
      {
        "id": "40000000005",
        "_tenant_id": "acme-corp",
        "dealname": "Stark Industries - Global Rollout",
        "amount": 100000.0,
        "dealstage": "contractsent",
        "pipeline": "default",
        "closedate": "2027-01-07T17:00:00+00:00",
        "createdate": "2026-11-08T10:00:00+00:00",
        "hs_lastmodifieddate": "2026-11-08T10:05:00+00:00",
        "dealtype": "newbusiness",
        "description": "Global rollout across 14 sites.",
        "hs_priority": "high",
        "hs_deal_stage_probability": 0.9,
        "hs_is_closed": false,
        "hs_is_closed_won": false,
        "days_to_close": 60,
        "hs_object_id": 40000000005,
        "created_at": "2026-11-08T10:00:00+00:00",
        "updated_at": "2026-11-08T10:05:00+00:00",
        "archived": false,
        "_scan_id": "hubspot-deals-scan-001",
        "_extracted_at": "2026-11-08T13:36:30.112000+00:00",
        "_page_number": 1,
        "_source_service": "hubspot_deals",
        "_dlt_load_id": "1794144990.12",
        "_dlt_id": "Vb0Qm3sQ0b2c7A"
      }
    ],
    "pagination": { "total": 5, "limit": 100, "offset": 0, "hasMore": false, "totalPages": 1 },
    "scanId": "hubspot-deals-scan-001"
  }
}
```
`NUMERIC` values are serialised as JSON numbers and timestamps as ISO-8601 UTC strings.

#### Status Codes
| Code | Meaning |
|---|---|
| 200 | OK |
| 400 | Scan not completed / invalid pagination |
| 404 | Unknown scan or table |

> The template's *Download Extraction Results* (CSV/Excel) endpoint is **not part of the generated code**, so it is not offered. Query Postgres directly or page through `/result`.

---

## 🛠️ Pipeline & Maintenance Endpoints

### Pipeline Info — `GET /api/pipeline/info`
```json
{
  "success": true,
  "data": {
    "pipeline_name": "hubspot_deals_extraction",
    "destination_type": "postgres",
    "source_type": "hubspot_deals",
    "database_health": { "healthy": true, "database": "hubspot_deals_data_dev", "host": "postgres_dev" },
    "supports_checkpoints": true
  }
}
```

### Cleanup — `POST /api/maintenance/cleanup`
Body `{"daysOld": 30}` (1-365, default 7). Deletes scan records older than N days.

### Detect Crashed — `POST /api/maintenance/detect-crashed?timeoutMinutes=10`
Marks `running` scans with no heartbeat for `timeoutMinutes` (1-60) as `crashed`, so they can be resumed.

---

## 🏥 Health & Stats Endpoints

### 1. Health Check

**Endpoint**: `GET /health` (lightweight; used by Docker healthchecks) and `GET /api/health` (adds pipeline info)

#### Response (Healthy)
```json
{
  "checks": { "database": "healthy" },
  "service": "hubspot_deals",
  "status": "healthy",
  "timestamp": "2026-11-08T13:31:44.100673+00:00",
  "version": "1.0.0"
}
```

#### Response (Unhealthy)
```json
{
  "checks": { "database": "unhealthy" },
  "service": "hubspot_deals",
  "status": "unhealthy",
  "timestamp": "2026-11-08T13:50:00.000000+00:00",
  "version": "1.0.0"
}
```

#### Status Codes
| Code | Meaning |
|---|---|
| 200 | Healthy |
| 503 | Database unreachable (`/health`) |
| 500 | Health check error (`/api/health`) |

### 2. Service Statistics

**Endpoint**: `GET /api/stats`

```json
{
  "success": true,
  "data": {
    "service": { "name": "data_extraction_service", "source_type": "hubspot_deals", "uptime": "..." },
    "jobs": { "total_jobs": 7, "status_breakdown": { "completed": 7 }, "total_records_extracted": 35 },
    "database": { },
    "performance": { "total_records_extracted": 35 }
  }
}
```

---

## ⚠️ Error Handling

### Error Response Formats

#### Validation Errors (400)
See [Error Response (Validation)](#error-response-validation). Also returned for a missing body: `{"success": false, "message": "No JSON data provided"}`.

#### Authentication Errors (401)
Service API key enabled and missing or wrong:
```json
{ "success": false, "message": "Missing or invalid X-API-Key header", "error": "unauthorized" }
```
Invalid HubSpot token on `validate-credentials`:
```json
{ "success": false, "message": "Invalid HubSpot access token",
  "data": { "valid": false, "has_deals_scope": false,
            "error": "Authentication credentials not found. | status=401 | category=INVALID_AUTHENTICATION | correlationId=..." } }
```

#### Authorization Errors (403)
```json
{ "success": false, "message": "Token lacks crm.objects.deals.read scope", "data": { "valid": true, "has_deals_scope": false } }
```

#### Not Found Errors (404)
```json
{ "success": false, "message": "No scan found with ID: nope", "error": "No scan found with ID: nope" }
```

#### Conflict Errors (409)
```json
{ "success": false, "message": "A scan with ID 'hubspot-deals-scan-001' already exists", "error": "A scan with ID 'hubspot-deals-scan-001' already exists" }
```

#### Rate Limit Errors (429)
The service does not rate-limit its own API. HubSpot `429`s are absorbed internally (client-side limiter, `Retry-After` retries). Only if HubSpot keeps refusing after `HUBSPOT_MAX_RETRIES` does the scan fail, with `errorMessage` containing `status=429 | category=RATE_LIMITS`.

#### Server Errors (500)
```json
{ "success": false, "message": "An unexpected error occurred: <detail>", "error": "<detail>" }
```

### Common Error Codes
| HTTP | Where | Cause | Fix |
|---|---|---|---|
| 400 | start | invalid `scanId` chars, `type` ≠ `deals`, short token, bad dates, `batchSize` outside 1-100 | Fix the request |
| 400 | pause/resume/cancel | wrong state | Check `status` first |
| 401 | any `/api/*` | missing `X-API-Key` (when enabled) | Send the header |
| 401 | validate-credentials | bad HubSpot token | Re-copy or rotate the token |
| 403 | validate-credentials | missing `crm.objects.deals.read` | Add the scope to the private app |
| 404 | status/results | unknown scan | Check `scanId` |
| 409 | start | `scanId` reused | Use a new ID |
| scan `failed` | async | HubSpot 401/403/5xx, DB down | Read `errorMessage` |

---

## 📚 Examples

### Complete Extraction Workflow

#### 1. Validate the token
```bash
export TOKEN=pat-na1-...
curl -s -X POST http://localhost:5200/api/scan/validate-credentials \
  -H "Content-Type: application/json" -d "{\"accessToken\":\"$TOKEN\"}"
```

#### 2. Start Extraction
```bash
curl -s -X POST http://localhost:5200/api/scan/start \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "scanId": "deals-'"$(date +%s)"'",
      "organizationId": "acme-corp",
      "type": ["deals"],
      "auth": { "accessToken": "'"$TOKEN"'" },
      "filters": { "batchSize": 100 }
    }
  }'
```

#### 3. Monitor Progress
```bash
curl -s http://localhost:5200/api/scan/$SCAN_ID/status | python -m json.tool
# loop until completed
until curl -s http://localhost:5200/api/scan/$SCAN_ID/status | grep -q '"status": "completed"'; do sleep 2; done
```

#### 4. Get Results
```bash
curl -s "http://localhost:5200/api/results/$SCAN_ID/tables"
curl -s "http://localhost:5200/api/results/$SCAN_ID/result?tableName=hubspot_deals&limit=100&offset=0"
```

#### 5. Pause / Resume (checkpoint test)
```bash
curl -s -X POST http://localhost:5200/api/scan/$SCAN_ID/pause
curl -s http://localhost:5200/api/scan/$SCAN_ID/status   # status=paused, phase=main_data_paused, cursor=<next page>
curl -s -X POST http://localhost:5200/api/scan/$SCAN_ID/resume
```

#### 6. Cancel Extraction (if needed)
```bash
curl -s -X POST http://localhost:5200/api/scan/$SCAN_ID/cancel
```

#### 7. Remove Extraction (cleanup)
```bash
curl -s -X DELETE http://localhost:5200/api/scan/$SCAN_ID/remove
```

### PowerShell Examples

#### Start Extraction
```powershell
$body = @{
  config = @{
    scanId = "deals-$(Get-Date -Format yyyyMMddHHmmss)"
    organizationId = "acme-corp"
    type = @("deals")
    auth = @{ accessToken = $env:HUBSPOT_ACCESS_TOKEN }
    filters = @{ batchSize = 100 }
  }
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri http://localhost:5200/api/scan/start -ContentType "application/json" -Body $body
```

#### Get Status
```powershell
Invoke-RestMethod -Uri "http://localhost:5200/api/scan/$scanId/status" | ConvertTo-Json -Depth 10
```

### Python Examples

#### Start Extraction
```python
import os, time, requests

BASE = "http://localhost:5200/api"
scan_id = f"deals-{int(time.time())}"
r = requests.post(f"{BASE}/scan/start", json={
    "config": {
        "scanId": scan_id,
        "organizationId": "acme-corp",
        "type": ["deals"],
        "auth": {"accessToken": os.environ["HUBSPOT_ACCESS_TOKEN"]},
        "filters": {"batchSize": 100},
    }
})
assert r.status_code == 202, r.text
```

#### Monitor Progress
```python
while True:
    data = requests.get(f"{BASE}/scan/{scan_id}/status").json()["data"]
    print(data["status"], data["recordsExtracted"])
    if data["status"] in ("completed", "failed", "cancelled"):
        break
    time.sleep(2)
if data["status"] == "failed":
    raise RuntimeError(data["errorMessage"])
```

#### Get Paginated Results
```python
deals, offset = [], 0
while True:
    page = requests.get(f"{BASE}/results/{scan_id}/result",
                        params={"tableName": "hubspot_deals", "limit": 500, "offset": offset}).json()["data"]
    deals += page["records"]
    if not page["pagination"]["hasMore"]:
        break
    offset += 500
print(len(deals), "deals")
```

#### Error Handling
```python
r = requests.post(f"{BASE}/scan/validate-credentials", json={"accessToken": token})
if r.status_code == 401:
    raise SystemExit("HubSpot token invalid: " + r.json()["data"]["error"])
if r.status_code == 403:
    raise SystemExit("Add the crm.objects.deals.read scope to the private app")
```

A complete automated version of this workflow, including database checks, lives in [`scripts/e2e_test.py`](../scripts/e2e_test.py).
