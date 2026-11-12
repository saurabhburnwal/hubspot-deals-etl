# HubSpot Deals ETL

Extracts **HubSpot CRM deals** into **PostgreSQL** with [dlt](https://dlthub.com), behind a Flask-RESTX API with Swagger docs. Scans run in the background with cursor pagination, checkpoints, pause/resume/cancel, rate limiting and per-tenant isolation.

Generated with the Glynac **DLT Generator** (`python dlt_generator.py -c hubspot-deals-config.json`) and then implemented for HubSpot Deals. Generator issues found and fixed along the way are listed in [`test-results/GENERATOR-ISSUES.md`](test-results/GENERATOR-ISSUES.md).

| | |
|---|---|
| Service name | `hubspot_deals` |
| Ports | dev **5200** · stage 5201 · prod 5202 |
| Source | HubSpot CRM API v3 `GET /crm/v3/objects/deals` |
| Destination | Postgres schema `hubspot_deals_<organizationId>`, table `hubspot_deals` |
| Swagger UI | http://localhost:5200/docs/ |

## Documentation
| Document | Contents |
|---|---|
| [docs/api-integration.md](docs/api-integration.md) | HubSpot API: auth, deals endpoint, parameters, response, properties, rate limits, errors |
| [docs/database-schema.md](docs/database-schema.md) | Tables, HubSpot→Postgres type mapping, DDL, indexes, multi-tenant design |
| [docs/api-documentation.md](docs/api-documentation.md) | This service's REST endpoints with request/response examples |
| [docs/hubspot-setup.md](docs/hubspot-setup.md) | Developer account, test account, private app and test deals (Phase 2) |
| [test-results/](test-results/) | Unit/E2E reports, health checks, DB verification, test deal IDs |

---

## Quick start

**Requirements**: Docker with Compose v2. The helper scripts in `scripts/` need only Python 3.9+ (standard library).

```bash
cp .env.example .env              # dev defaults; never commit .env
docker compose up -d --build      # postgres_dev + redis + hubspot_deals_service_dev
curl http://localhost:5200/health
# {"checks":{"database":"healthy"},"service":"hubspot_deals","status":"healthy",...}
open http://localhost:5200/docs/  # Swagger UI
```

### Run a scan
```bash
export TOKEN=pat-na1-...          # HubSpot private app token (crm.objects.deals.read)

# 1. check the token
curl -s -X POST localhost:5200/api/scan/validate-credentials \
  -H 'Content-Type: application/json' -d "{\"accessToken\":\"$TOKEN\"}"

# 2. start
curl -s -X POST localhost:5200/api/scan/start -H 'Content-Type: application/json' -d '{
  "config": {"scanId": "deals-001", "organizationId": "acme-corp", "type": ["deals"],
             "auth": {"accessToken": "'"$TOKEN"'"}, "filters": {}}}'

# 3. poll, then read the results
curl -s localhost:5200/api/scan/deals-001/status
curl -s "localhost:5200/api/results/deals-001/result?limit=100"
```

Or query Postgres directly:
```bash
docker exec -it hubspot_deals_postgres_dev psql -U postgres -d hubspot_deals_data_dev \
  -c "select id, dealname, amount, dealstage, closedate from hubspot_deals_acme_corp.hubspot_deals order by amount"
```

### Pause / resume / cancel
```bash
curl -X POST localhost:5200/api/scan/deals-001/pause    # stops at the next page boundary, saves cursor
curl -X POST localhost:5200/api/scan/deals-001/resume   # continues from the saved cursor
curl -X POST localhost:5200/api/scan/deals-001/cancel
```

---

## Testing

```bash
# Unit tests (12): pagination, auth errors, 429 retry, rate limiter, type conversion, checkpoint pause/resume
docker exec hubspot_deals_service_dev python -m unittest tests.test_hubspot_deals -v

# Seed the 5 assessment test deals (token needs crm.objects.deals.write too) -> test-results/test-deals.json
HUBSPOT_ACCESS_TOKEN=$TOKEN python scripts/seed_test_deals.py

# Export the portal's deal properties/pipelines -> test-results/deal-properties.md
HUBSPOT_ACCESS_TOKEN=$TOKEN python scripts/export_deal_properties.py

# End-to-end against real HubSpot (health, docs, scan, DB verification, pause/resume, restart)
HUBSPOT_TEST_DELAY_SECONDS=2 HUBSPOT_CHECKPOINT_INTERVAL=1 docker compose up -d hubspot_deals_service_dev   # slow pages + checkpoint per page so a pause lands mid-scan
HUBSPOT_ACCESS_TOKEN=$TOKEN python scripts/e2e_test.py --label hubspot
docker compose up -d hubspot_deals_service_dev                                 # back to normal speed
```

**Offline E2E** (no HubSpot account): `tests/mock_hubspot.py` implements the CRM v3 endpoints used here.
```bash
HUBSPOT_API_BASE_URL=http://127.0.0.1:8099 HUBSPOT_TEST_DELAY_SECONDS=1 HUBSPOT_CHECKPOINT_INTERVAL=1 docker compose up -d hubspot_deals_service_dev
docker exec -d hubspot_deals_service_dev python tests/mock_hubspot.py 8099
python scripts/e2e_test.py --label mock --token pat-mock-valid --expected-count 5
```

---

## Configuration

All settings are environment variables (`config.py`). `docker-compose.yml` sets dev values; values in `.env` override the `${VAR:-default}` entries. The full list with comments is in [.env.example](.env.example).

| Variable | Default | Purpose |
|---|---|---|
| `HUBSPOT_API_BASE_URL` | `https://api.hubapi.com` | HubSpot API host (point at the mock for offline tests) |
| `HUBSPOT_API_TIMEOUT` | `30` | Per-request timeout (s) |
| `HUBSPOT_RATE_LIMIT_REQUESTS` / `_WINDOW_SECONDS` | `150` / `10` | Client-side limiter (use 100 for Free/Starter portals) |
| `HUBSPOT_MAX_RETRIES` / `HUBSPOT_RETRY_BACKOFF_SECONDS` | `3` / `1` | Retries for 429/5xx/network errors |
| `HUBSPOT_PAGE_SIZE` | `100` | Deals per request (max 100) |
| `HUBSPOT_CHECKPOINT_INTERVAL` | `10` | Checkpoint every N pages |
| `HUBSPOT_MAX_PAGES` | `10000` | Safety stop |
| `HUBSPOT_TEST_DELAY_SECONDS` | `0` | Testing only: sleep before each HubSpot call |
| `DB_*`, `DESTINATION__POSTGRES__CREDENTIALS__*` | dev Postgres | Control-plane DB and dlt destination |
| `DLT_PIPELINE_NAME` | `hubspot_deals_pipeline_dev` | Pipeline name |
| `CONFIG_PASSWORD` | dev value | Key material for encrypting stored access tokens; **change it outside dev** |
| `SERVICE_API_KEY` | empty | If set, `/api/*` requires `X-API-Key` |

The HubSpot token is **not** an environment setting for the service. It is sent per scan, encrypted at rest, and never logged. `HUBSPOT_ACCESS_TOKEN` in `.env` is read only by the helper scripts.

---

## How it works

```
POST /api/scan/start ─► jobs row (pending, token encrypted) ─► 202
                              │ worker thread
                              ▼
        HubSpotAPIService ── validate token ── property metadata (types)
                              │
        loop pages: GET /crm/v3/objects/deals?limit=100&after=<cursor>
           ├ pause/cancel check between pages
           ├ transform: strings → Decimal / timestamptz / bool / bigint + _tenant_id/_scan_id/_extracted_at
           ├ yield page to dlt
           └ checkpoint every N pages (next cursor)
                              ▼
        dlt merge → hubspot_deals_<tenant>.hubspot_deals  (key: _tenant_id, id)
        ensure indexes → job completed
```

| File | Role |
|---|---|
| `services/hubspot_api_service.py` | HubSpot client: bearer auth, `get_deals()` with cursor paging, sliding-window limiter + header-adaptive throttle, 429/5xx retries, typed exceptions, credential validation |
| `services/data_source.py` | dlt resource `hubspot_deals`: pagination, checkpoints, type conversion, metadata, merge disposition |
| `services/extraction_service.py` | Orchestration: job lifecycle, resume rules, pipeline run, index creation |
| `api/routes.py`, `api/schemas.py` | REST endpoints and request validation |
| `tests/` | Mock HubSpot + unit tests |
| `scripts/` | Seed test deals, export properties, E2E test |

### Design decisions
- **Merge, not replace.** The template wrote with `replace`, so resuming a paused scan would have dropped the rows loaded before the pause. Upserting on `(_tenant_id, id)` makes resume, re-run and crash restart idempotent.
- **Safe resume.** A scan resumes from a cursor only from a *pause* checkpoint, which is written after a graceful stop, when dlt has loaded every earlier row. After a crash it restarts from page 1, because rows extracted after the last load may never have been committed.
- **Typed columns named after HubSpot properties**, typed from the portal's property metadata, so a row maps 1:1 to the API object and custom properties work automatically.
- **Schema per tenant, plus `_tenant_id` in the key.** This isolates tenants physically and leaves the door open to a shared table with row-level security.

---

## Environments
```bash
docker compose up -d                                              # dev  :5200
docker compose --profile stage up -d postgres_stage hubspot_deals_service_stage   # :5201
docker compose --profile prod  up -d postgres_prod  hubspot_deals_service_prod    # :5202 (gunicorn)
docker compose --profile dev up -d pgadmin redis_commander        # pgAdmin :8080, Redis Commander :8081
```
For production, set strong `SECRET_KEY`, `CONFIG_PASSWORD`, `DB_PASSWORD` and `SERVICE_API_KEY`. The compose files contain dev placeholders only.

## Troubleshooting
| Symptom | Fix |
|---|---|
| `unauthorized: personal access token is expired` while pulling images | Your Docker Hub login has expired: `docker logout` (or `docker login`), then rebuild. Public images need no login. |
| Scan `failed` with `HubSpot authentication failed` | Token wrong or rotated; check with `/api/scan/validate-credentials` |
| Scan `failed` with `missing the crm.objects.deals.read scope` | Add the scope to the private app and commit the change |
| Pause arrives after the scan already finished | Small portals finish in about 1 s; start the service with `HUBSPOT_TEST_DELAY_SECONDS=2 HUBSPOT_CHECKPOINT_INTERVAL=1` and use `filters.batchSize=1` to test. A pause that arrives after the last page completes the scan instead. |
| Port 5432 already in use | Stop the local Postgres or change the published port in `docker-compose.yml` |
| Logs | `docker logs -f hubspot_deals_service_dev` (JSON lines) |
