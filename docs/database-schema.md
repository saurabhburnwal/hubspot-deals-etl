# 🗄️ HubSpot Deals ETL - Database Schema

PostgreSQL schema for the **hubspot-deals-etl** service: the scan-job control tables, the extracted `hubspot_deals` table, how HubSpot property types map to PostgreSQL types, indexes, and multi-tenant isolation.

> Generated from the DLT Generator template `docs/DATABASE-DESIGN-DOCS.md` and customised for HubSpot Deals.
> The DDL below was taken from a running instance with `pg_dump -s`, so it matches what the service creates.

---

## 📋 Overview

| Layer | Schema | Tables | Created by |
|---|---|---|---|
| **Control plane** (scan jobs) | `public` | `jobs`, `job_checkpoints` | SQLAlchemy `Base.metadata.create_all()` at startup (`models/models.py`) |
| **Extracted data**, one schema per tenant | `hubspot_deals_<tenant>` | `hubspot_deals` + dlt bookkeeping (`_dlt_loads`, `_dlt_pipeline_state`, `_dlt_version`) | dlt on first load; indexes by `ExtractionService._ensure_deal_indexes()` |
| dlt merge staging | `hubspot_deals_<tenant>_staging` | `hubspot_deals`, `_dlt_version` | dlt (transient rows used by the merge) |

`<tenant>` is the scan's `organizationId`, lowercased, with every character outside `[a-z0-9_]` replaced by `_` (`utils.build_dataset_name`). Example: `organizationId = "acme-corp"` → schema `hubspot_deals_acme_corp`.

```
public.jobs (1) ──< public.job_checkpoints (N)          control plane
     │ id = scanId
     │ metadata.dataset_name ─────────────┐
                                          ▼
                     hubspot_deals_<tenant>.hubspot_deals   data plane
                         _scan_id = jobs.id (last scan that wrote the row)
                         _tenant_id = jobs."organizationId"
```

---

## 🏗️ Table Schemas

### 1. `public.jobs` (ScanJob)

**Purpose**: One row per scan: lifecycle status, encrypted config, result metadata.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | VARCHAR(255) | **PRIMARY KEY** | `scanId` from the request. The PK guarantees a scan ID is used once; the API returns 409 on reuse. |
| `organizationId` | VARCHAR(255) | NOT NULL, INDEX | Tenant ID → selects the data schema |
| `type` | VARCHAR(50) | NOT NULL, default `'deals'` | Scan type |
| `status` | VARCHAR(50) | NOT NULL, default `'pending'` | `pending`, `running`, `paused`, `resuming`, `completed`, `failed`, `cancelled`, `crashed` |
| `startTime` | TIMESTAMPTZ | NOT NULL, default `now()` | Scan created |
| `endTime` | TIMESTAMPTZ | NULL | Completed / failed / cancelled time |
| `lastHeartbeat` | TIMESTAMPTZ | NULL | Updated at each checkpoint; used by crash detection |
| `recordsExtracted` | INTEGER | default 0 | Deals loaded |
| `errorMessage` | TEXT | NULL | Failure reason (e.g. `HubSpot authentication failed: ...`) |
| `config` | JSON | NULL | `{"auth": "<Fernet-encrypted blob>", "filters": {...}, "type": ["deals"]}`. **The access token is never stored in plaintext.** |
| `job_metadata` | JSON | NULL | `dataset_name`, `pipeline_name`, `table_record_counts`, `completed_at`, resume and error details |

### 2. `public.job_checkpoints`

**Purpose**: Progress snapshots that make pause/resume and crash recovery possible.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | SERIAL | PRIMARY KEY | |
| `job_id` | VARCHAR(255) | FK → `jobs.id` ON DELETE CASCADE (ORM), INDEX | |
| `createdAt` | TIMESTAMPTZ | NOT NULL, default `now()` | |
| `phase` | VARCHAR(50) | NOT NULL | `main_data` (every N pages), `main_data_paused`, `main_data_cancelled`, `main_data_error`, `main_data_completed` |
| `recordsProcessed` | INTEGER | | Deals extracted so far |
| `cursor` | VARCHAR(500) | NULL | HubSpot `after` cursor of the **next** page to fetch (NULL when complete) |
| `pageNumber` | INTEGER | | Pages processed |
| `batchSize` | INTEGER | | HubSpot page size used |
| `checkpoint_data` | JSON | | `tenant_id`, pause/cancel reason, error, final API usage headers |
| `totalEstimated`, `lastProcessedId`, `lastProcessedTimestamp` | | NULL | Reserved by the template (unused) |

**Resume rule**: only a `main_data_paused` checkpoint is resumed from its cursor. That checkpoint is written when the extractor exits gracefully, so dlt has loaded every row before the cursor. Any other checkpoint (periodic, error, crash) restarts from page 1, because rows yielded since the last load may not have been committed. The merge key makes re-reading idempotent.

### 3. `hubspot_deals_<tenant>.hubspot_deals` (Result table)

**Purpose**: One row per HubSpot deal per tenant, with typed columns.

The column names are the HubSpot internal property names, so a row maps 1:1 to the API object. The columns below are the **core properties** requested on every scan. Extra properties requested with `filters.properties` (or `["*"]`) become additional columns via dlt schema evolution, typed by the HubSpot property metadata (see the type mapping below).

#### Identity
| Column | PostgreSQL type | Null | Source | Description |
|---|---|---|---|---|
| `id` | VARCHAR | NOT NULL | `results[].id` | HubSpot deal ID |
| `_tenant_id` | VARCHAR | NOT NULL | scan `organizationId` | Tenant. **`(_tenant_id, id)` is the merge/primary key** |
| `hs_object_id` | BIGINT | | property | Same value as `id`, numeric |

#### Deal properties
| Column | PostgreSQL type | HubSpot type | Description |
|---|---|---|---|
| `dealname` | VARCHAR | string | Deal name |
| `amount` | NUMERIC(18,2) | number | Amount in deal currency |
| `dealstage` | VARCHAR | enumeration | Stage ID (`qualifiedtobuy`, `closedwon`, ...) |
| `pipeline` | VARCHAR | enumeration | Pipeline ID |
| `closedate` | TIMESTAMPTZ | datetime | Expected/actual close |
| `createdate` | TIMESTAMPTZ | datetime | Created in HubSpot |
| `hs_lastmodifieddate` | TIMESTAMPTZ | datetime | Last modified in HubSpot |
| `dealtype` | VARCHAR | enumeration | `newbusiness` / `existingbusiness` |
| `description` | VARCHAR | string | Description |
| `hubspot_owner_id` | VARCHAR | enumeration | Owner user ID |
| `hs_priority` | VARCHAR | enumeration | `low` / `medium` / `high` |
| `deal_currency_code` | VARCHAR | enumeration | ISO currency |
| `amount_in_home_currency` | NUMERIC(18,2) | number | Amount in company currency |
| `hs_deal_stage_probability` | NUMERIC(5,4) | number | 0.0000-1.0000 |
| `hs_forecast_amount` | NUMERIC(18,2) | number | Forecast amount |
| `hs_forecast_probability` | NUMERIC(5,4) | number | Forecast probability |
| `hs_projected_amount` | NUMERIC(18,2) | number | amount × stage probability |
| `hs_closed_amount` | NUMERIC(18,2) | number | Amount if won |
| `hs_is_closed` | BOOLEAN | bool | In a closed stage |
| `hs_is_closed_won` | BOOLEAN | bool | Closed won |
| `days_to_close` | BIGINT | number | Days create → close |
| `hs_next_step` | VARCHAR | string | Next step |
| `closed_lost_reason` | VARCHAR | string | Lost reason |
| `closed_won_reason` | VARCHAR | string | Won reason |
| `hs_analytics_source` | VARCHAR | enumeration | Original source |
| `num_associated_contacts` | BIGINT | number | Contact count |
| `num_contacted_notes` | BIGINT | number | Sales activities |
| `num_notes` | BIGINT | number | Notes/activities |
| `notes_last_updated` | TIMESTAMPTZ | datetime | Last activity |

#### Record timestamps
| Column | PostgreSQL type | Source |
|---|---|---|
| `created_at` | TIMESTAMPTZ | `results[].createdAt` |
| `updated_at` | TIMESTAMPTZ | `results[].updatedAt` |
| `archived` | BOOLEAN | `results[].archived` |
| `archived_at` | TIMESTAMPTZ | `results[].archivedAt` |

#### ETL metadata
| Column | PostgreSQL type | Null | Description |
|---|---|---|---|
| `_extracted_at` | TIMESTAMPTZ | NOT NULL | When the page containing this deal was fetched (UTC) |
| `_scan_id` | VARCHAR | NOT NULL | Scan that last wrote the row (→ `public.jobs.id`) |
| `_tenant_id` | VARCHAR | NOT NULL | Tenant (see Identity) |
| `_page_number` | BIGINT | | HubSpot page number within the scan |
| `_source_service` | VARCHAR | | Always `hubspot_deals` |
| `_dlt_load_id` | VARCHAR | NOT NULL | dlt load package ID (→ `_dlt_loads.load_id`) |
| `_dlt_id` | VARCHAR | NOT NULL, UNIQUE | dlt row ID |

---

## 🔁 HubSpot → PostgreSQL Type Mapping

HubSpot returns **every property value as a string**. `services/data_source.py::convert_property` converts them using the type reported by `GET /crm/v3/properties/deals`. If that endpoint is unavailable it uses a static map of the core properties. Explicit dlt column hints (`COLUMN_HINTS`) fix the PostgreSQL types of the core columns even when the first load has only NULLs.

| HubSpot `type` (`fieldType`) | Raw example | Python | PostgreSQL | Notes |
|---|---|---|---|---|
| `string` (text, textarea, html) | `"Upsell"` | `str` | VARCHAR | |
| `enumeration` (select, radio, checkbox) | `"closedwon"` | `str` | VARCHAR | Multi-select values are `;`-separated |
| `number` (money/amount) | `"25000.50"` | `Decimal` | NUMERIC(18,2) | `Decimal`, never float, so money is exact |
| `number` (probability) | `"0.6"` | `Decimal` | NUMERIC(5,4) | |
| `number` (counts / IDs) | `"30"` | `int` | BIGINT | `days_to_close`, `num_*`, `hs_object_id` |
| `number` (other / custom) | `"12.5"` | `Decimal` | NUMERIC(38,9) | dlt default precision |
| `datetime` | `"2026-12-31T17:00:00Z"` / `"1700000000000"` | aware `datetime` | TIMESTAMPTZ | ISO-8601 and epoch-ms both handled; stored in UTC |
| `date` | `"2026-12-31"` | `date` | DATE | |
| `bool` (booleancheckbox) | `"true"` | `bool` | BOOLEAN | |
| `phone_number` | `"+1 555..."` | `str` | VARCHAR | |
| any | `""` / `null` | `None` | NULL | Empty strings become NULL |

---

## 📜 DDL (CREATE TABLE statements)

### Control plane
```sql
CREATE TABLE public.jobs (
    id                 VARCHAR(255) PRIMARY KEY,
    "organizationId"   VARCHAR(255) NOT NULL,
    type               VARCHAR(50)  NOT NULL DEFAULT 'deals',
    status             VARCHAR(50)  NOT NULL DEFAULT 'pending',
    "startTime"        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    "endTime"          TIMESTAMPTZ,
    "lastHeartbeat"    TIMESTAMPTZ,
    "recordsExtracted" INTEGER DEFAULT 0,
    "errorMessage"     TEXT,
    config             JSON,
    job_metadata       JSON
);
CREATE INDEX ix_jobs_organizationId ON public.jobs ("organizationId");

CREATE TABLE public.job_checkpoints (
    id                       SERIAL PRIMARY KEY,
    job_id                   VARCHAR(255) NOT NULL REFERENCES public.jobs(id),
    "createdAt"              TIMESTAMPTZ NOT NULL DEFAULT now(),
    phase                    VARCHAR(50) NOT NULL,
    "recordsProcessed"       INTEGER DEFAULT 0,
    "totalEstimated"         INTEGER,
    cursor                   VARCHAR(500),
    "pageNumber"             INTEGER DEFAULT 0,
    "batchSize"              INTEGER DEFAULT 100,
    "lastProcessedId"        VARCHAR(255),
    "lastProcessedTimestamp" TIMESTAMPTZ,
    checkpoint_data          JSON
);
CREATE INDEX ix_job_checkpoints_job_id ON public.job_checkpoints (job_id);
```

### Deals table (per tenant schema, as created by dlt)
```sql
CREATE SCHEMA IF NOT EXISTS hubspot_deals_acme_corp;

CREATE TABLE hubspot_deals_acme_corp.hubspot_deals (
    id                        VARCHAR       NOT NULL,
    _tenant_id                VARCHAR       NOT NULL,
    dealname                  VARCHAR,
    amount                    NUMERIC(18,2),
    dealstage                 VARCHAR,
    pipeline                  VARCHAR,
    closedate                 TIMESTAMPTZ,
    createdate                TIMESTAMPTZ,
    hs_lastmodifieddate       TIMESTAMPTZ,
    dealtype                  VARCHAR,
    description               VARCHAR,
    hubspot_owner_id          VARCHAR,
    hs_priority               VARCHAR,
    deal_currency_code        VARCHAR,
    amount_in_home_currency   NUMERIC(18,2),
    hs_deal_stage_probability NUMERIC(5,4),
    hs_forecast_amount        NUMERIC(18,2),
    hs_forecast_probability   NUMERIC(5,4),
    hs_projected_amount       NUMERIC(18,2),
    hs_closed_amount          NUMERIC(18,2),
    hs_is_closed              BOOLEAN,
    hs_is_closed_won          BOOLEAN,
    days_to_close             BIGINT,
    hs_next_step              VARCHAR,
    closed_lost_reason        VARCHAR,
    closed_won_reason         VARCHAR,
    hs_analytics_source       VARCHAR,
    num_associated_contacts   BIGINT,
    num_contacted_notes       BIGINT,
    num_notes                 BIGINT,
    notes_last_updated        TIMESTAMPTZ,
    hs_object_id              BIGINT,
    created_at                TIMESTAMPTZ,
    updated_at                TIMESTAMPTZ,
    archived                  BOOLEAN,
    archived_at               TIMESTAMPTZ,
    _scan_id                  VARCHAR       NOT NULL,
    _extracted_at             TIMESTAMPTZ   NOT NULL,
    _page_number              BIGINT,
    _source_service           VARCHAR,
    _dlt_load_id              VARCHAR       NOT NULL,
    _dlt_id                   VARCHAR       NOT NULL,
    CONSTRAINT hubspot_deals__dlt_id_key UNIQUE (_dlt_id)
);
```

---

## ⚡ Indexes

dlt creates only the `_dlt_id` unique constraint. After each successful load the service runs these idempotent statements (`ExtractionService.DEAL_INDEXES`), so a new tenant schema gets them on its first scan:

```sql
-- Merge key: one row per deal per tenant (also enforces the dlt merge contract)
CREATE UNIQUE INDEX IF NOT EXISTS uq_hubspot_deals_tenant_id      ON hubspot_deals ("_tenant_id", "id");

-- Tenant-scoped filters used by reporting/dashboards
CREATE INDEX IF NOT EXISTS idx_hubspot_deals_tenant_stage        ON hubspot_deals ("_tenant_id", "dealstage");
CREATE INDEX IF NOT EXISTS idx_hubspot_deals_tenant_closedate    ON hubspot_deals ("_tenant_id", "closedate");
CREATE INDEX IF NOT EXISTS idx_hubspot_deals_tenant_createdate   ON hubspot_deals ("_tenant_id", "createdate");
CREATE INDEX IF NOT EXISTS idx_hubspot_deals_tenant_modified     ON hubspot_deals ("_tenant_id", "hs_lastmodifieddate");

-- Pipeline/stage funnel analysis
CREATE INDEX IF NOT EXISTS idx_hubspot_deals_pipeline_stage      ON hubspot_deals ("pipeline", "dealstage");

-- "Which rows did scan X write?" (results API, audits)
CREATE INDEX IF NOT EXISTS idx_hubspot_deals_scan                ON hubspot_deals ("_scan_id");

-- Open-pipeline queries ("deals closing this month") - partial index stays small
CREATE INDEX IF NOT EXISTS idx_hubspot_deals_open_closedate      ON hubspot_deals ("closedate")
    WHERE "hs_is_closed" IS NOT TRUE;
```

| Index | Serves |
|---|---|
| `uq_hubspot_deals_tenant_id` | Merge upserts, point lookups by deal ID |
| `idx_..._tenant_stage` | Stage distribution, funnel counts |
| `idx_..._tenant_closedate` | Close-date ranges, forecasts |
| `idx_..._tenant_createdate` | Cohorts, the `dateRange` filter |
| `idx_..._tenant_modified` | Incremental-sync watermark queries |
| `idx_..._pipeline_stage` | Per-pipeline funnels |
| `idx_..._scan` | Results API, scan audits |
| `idx_..._open_closedate` | Open-deal dashboards |

Every composite index leads with `_tenant_id`. That keeps them effective if tenants are ever consolidated into one shared table, which is the alternative design below.

---

## 🛡️ Multi-Tenant Data Isolation

**Chosen design: schema-per-tenant + tenant column.**

1. **Schema per tenant**: each `organizationId` loads into its own schema `hubspot_deals_<tenant>` (the dlt `dataset_name`). Tenants never share a table, so a query without a tenant filter cannot return another tenant's deals, and a tenant can be exported or dropped with `DROP SCHEMA ... CASCADE`.
2. **`_tenant_id` on every row** and in the primary key `(_tenant_id, id)`. This guards against a mis-routed load, makes rows self-describing when copied to a warehouse, and supports consolidation later.
3. **Per-tenant credentials**: each scan carries its tenant's own HubSpot token, so one tenant's token can never read another portal. Tokens are encrypted at rest in `jobs.config`.
4. **Control plane** rows are keyed by `organizationId`; `GET /api/scan/list?organizationId=` filters by it.

**Production hardening (recommended):**
```sql
-- One login role per tenant, limited to its own schema
CREATE ROLE tenant_acme_corp NOLOGIN;
GRANT USAGE ON SCHEMA hubspot_deals_acme_corp TO tenant_acme_corp;
GRANT SELECT ON ALL TABLES IN SCHEMA hubspot_deals_acme_corp TO tenant_acme_corp;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
```

**Alternative: shared table + Row-Level Security** (for thousands of small tenants, where thousands of schemas become unwieldy):
```sql
CREATE TABLE hubspot.deals (LIKE hubspot_deals_acme_corp.hubspot_deals INCLUDING ALL);
ALTER TABLE hubspot.deals ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON hubspot.deals
    USING (_tenant_id = current_setting('app.tenant_id'));
-- the application runs: SET app.tenant_id = 'acme-corp';
```
The composite indexes above already lead with `_tenant_id`, so they work unchanged for this design.

---

## 🔗 Relationships

### Primary Relationships
- `jobs.id` 1 ──< N `job_checkpoints.job_id`
- `jobs.id` ← `hubspot_deals._scan_id`: the scan that last wrote each deal. This is a logical link, not a foreign key, because the tables live in different schemas and deals outlive scans.
- `jobs.job_metadata->>'dataset_name'` → tenant schema name
- `hubspot_deals._dlt_load_id` → `_dlt_loads.load_id`

### Cascade Behavior
- Deleting a job deletes its checkpoints (`cascade="all, delete-orphan"`).
- `DELETE /api/scan/{id}/remove` deletes the job, its checkpoints, **and the deal rows whose `_scan_id` is that scan** (`DatabaseService.remove_dataset_tables`). Because merge rewrites `_scan_id` on every load, these are the rows the scan last wrote. Deals last written by other scans of the tenant are kept.

---

## 📊 Common Queries

### Basic Scan Management
```sql
-- Latest scans for a tenant
SELECT id, status, "recordsExtracted", "startTime", "endTime", "errorMessage"
FROM public.jobs WHERE "organizationId" = 'acme-corp'
ORDER BY "startTime" DESC LIMIT 20;

-- Checkpoint trail of a scan
SELECT id, phase, "pageNumber", "recordsProcessed", cursor, "createdAt"
FROM public.job_checkpoints WHERE job_id = 'scan-001' ORDER BY id;

-- Possibly crashed jobs (no heartbeat for 10 min)
SELECT id FROM public.jobs
WHERE status = 'running' AND "lastHeartbeat" < now() - interval '10 minutes';
```

### Results Management
```sql
SET search_path = hubspot_deals_acme_corp;

-- Pipeline by stage
SELECT dealstage, count(*) AS deals, sum(amount) AS total_amount
FROM hubspot_deals WHERE _tenant_id = 'acme-corp' AND NOT archived
GROUP BY dealstage ORDER BY total_amount DESC;

-- Win rate
SELECT round(100.0 * count(*) FILTER (WHERE hs_is_closed_won) / NULLIF(count(*) FILTER (WHERE hs_is_closed), 0), 1) AS win_rate_pct
FROM hubspot_deals WHERE _tenant_id = 'acme-corp';

-- Open deals closing in the next 30 days (uses the partial index)
SELECT id, dealname, amount, dealstage, closedate
FROM hubspot_deals
WHERE hs_is_closed IS NOT TRUE AND closedate BETWEEN now() AND now() + interval '30 days'
ORDER BY closedate;

-- Rows written by a given scan
SELECT count(*) FROM hubspot_deals WHERE _scan_id = 'scan-001';
```

### Control Operations
```sql
-- Data freshness per tenant
SELECT _tenant_id, max(_extracted_at) AS last_extracted, count(*) FROM hubspot_deals GROUP BY 1;

-- Duplicate check (must return 0 rows)
SELECT _tenant_id, id, count(*) FROM hubspot_deals GROUP BY 1, 2 HAVING count(*) > 1;
```

---

## 🛠️ Implementation Notes

### Load strategy: `merge` on `(_tenant_id, id)`
The template used `write_disposition="replace"`. With replace, resuming a paused scan would have **dropped the rows loaded before the pause**. `merge` (dlt's `delete-insert` strategy, using the `_staging` schema) makes every load an upsert:
- Re-running a scan updates existing deals in place; it never duplicates them.
- A resumed scan adds the remaining pages.
- A crash restart re-reads from page 1 safely.

### Deleted deals
`merge` does not remove deals that were deleted in HubSpot. Run a scan with `filters.includeArchived = true` to load archived deals (`archived = true`, `archived_at` set), or switch the resource to `replace` for full-refresh semantics.

### Schema evolution
New properties requested later are added as new nullable columns by dlt. Existing columns are never retyped; a conflicting value goes to a variant column (`<name>__v_<type>`).

---

## 📈 Performance Considerations

### Indexing Strategy
See [Indexes](#-indexes). Every composite index leads with `_tenant_id`; date columns are TIMESTAMPTZ for range scans.

### Data Retention
```sql
-- Scan metadata older than N days (also: POST /api/maintenance/cleanup {"daysOld": 30})
DELETE FROM public.jobs WHERE "endTime" < now() - interval '30 days';
-- dlt staging rows are transient; the staging schema can be truncated safely between loads
```

### Large Result Sets
- The results API paginates (`limit` ≤ 500, `offset`).
- For portals with more than 1M deals, partition `hubspot_deals` by `createdate` (yearly) or move to the shared RLS table with hash partitioning on `_tenant_id`.

---

## 🛡️ Data Integrity

### Constraints
- `jobs.id` PRIMARY KEY: scan IDs are unique; it is also what makes duplicate-start detection race-free.
- `uq_hubspot_deals_tenant_id` UNIQUE `(_tenant_id, id)`: one row per deal per tenant.
- NOT NULL on `id`, `_tenant_id`, `_scan_id`, `_extracted_at`.
- `amount` is NUMERIC, never float, so money is exact.

### Validation performed by `scripts/e2e_test.py`
Row count ≥ expected, all seeded deal IDs present, zero duplicates on `(_tenant_id, id)`, no NULL metadata, column types match this document, and all indexes exist.
