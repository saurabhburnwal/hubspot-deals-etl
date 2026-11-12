# DLT Generator: issues and deviations found

The assessment asks to "document any issues or deviations from expected behavior". Each item below was found while generating and implementing `hubspot-deals-etl` with DLT Generator v2.0.0 (`dlt_generator.py`, template as of 2026-11-08), and each was fixed in this repository.

**Severity**: 🔴 breaks build/run · 🟠 wrong results or data loss · 🟡 incorrect but non-fatal · ⚪ cosmetic/docs

## Generation step — worked as documented
`python dlt_generator.py -c hubspot-deals-config.json` copied 32 files, replaced placeholders in 8, and applied the ports 5200/5201/5202. No `{{...}}` placeholders were left in the output. The `docs/` folder contained three templates (`INTEGRATION-DOCS.md`, `DATABASE-DESIGN-DOCS.md`, `APi-DOCS.md`), which were filled in and renamed to the deliverable names `api-integration.md`, `database-schema.md` and `api-documentation.md`.

## Issues in the generated project

| # | Sev | Where | Problem | Effect | Fix |
|---|---|---|---|---|---|
| 1 | 🔴 | `requirements.txt` | `cryptography==41.0.8` does not exist on PyPI (41.x ends at 41.0.7) | `docker compose up --build` fails at `pip install` | Pinned `cryptography==42.0.8`; pinned `dlt[postgres]==1.32.0` (was unpinned) |
| 2 | ⚪ | `docker-compose.yml` | `name: Hubspot_Deals DLT Extraction Service` is not a valid project name; Compose silently normalises it to `hubspot_dealsdltextractionservice` (verified with `docker compose config`) | Unexpected project/container label names | `name: hubspot-deals-etl` |
| 3 | 🟡 | `services/extraction_service.py` `start_scan` / `resume_scan` | Real work scheduled with `asyncio.create_task()` inside a coroutine that the route runs with `asyncio.run()`. `asyncio.run()` cancels pending tasks when `start_scan` returns. It works today only because the scan coroutine never suspends (`pipeline.run` is synchronous), so it finishes within its first step. Verified: with any real `await` inside, the task is cancelled after its first step. | Latent: the first `await` added to the scan path silently kills every scan | `await self._execute_scan_with_setup(...)` directly (already on a worker thread); resume runs `asyncio.run(_execute_scan)` on the executor |
| 4 | 🟠 | `api/routes.py` + `extraction_service` | Route checks "scan exists?" and then creates the job row later on a background thread (check-then-act race) | A duplicate request with the same `scanId` also gets 202; its failed INSERT then runs `fail_job(scanId)` and **marks the original scan failed**. Reproduced by the E2E suite. | Job row created synchronously in the route (`register_scan`); the primary key decides; duplicates get 409 |
| 5 | 🟠 | `services/data_source.py` | `write_disposition="replace"` | Resuming a paused scan replaces the table, **losing every row loaded before the pause** | `merge` on `(_tenant_id, id)` |
| 6 | 🟠 | `extraction_service.create_source_with_checkpoints` | Resumes from *any* checkpoint cursor, including periodic ones written before dlt has loaded the rows | After a crash, resume **skips** pages that were extracted but never committed | Resume from a cursor only for `main_data_paused`; otherwise restart (idempotent thanks to merge) |
| 7 | 🟠 | `extraction_service._execute_scan` | After `pipeline.run`, only `cancelled` is preserved | A **paused** scan is immediately marked `completed` | Keep `paused` and `cancelled` statuses |
| 8 | 🟡 | `extraction_service._execute_scan` | `complete_job()` called twice | Duplicate DB write and logs | Removed duplicate |
| 9 | 🟡 | `extraction_service._execute_scan_with_setup` | `if not check_database_health():` — the function returns a dict, which is always truthy | DB-down guard never fires | Check `.get("healthy")` |
| 10 | 🟡 | `job_service.get_job_statistics` | `total_records_extracted` ignores the `organizationId` filter | Tenant statistics show other tenants' record counts (4 jobs reported 35 records instead of 20) | Apply the same filter |
| 11 | 🟡 | `api/routes.py` | `pause` endpoint exists but there is no `resume` endpoint; `ExtractionService.resume_scan` used `create_task` with the same cancellation problem as #3 | Paused scans cannot be resumed | Added `POST /api/scan/{id}/resume` running on the executor |
| 12 | 🟡 | `api/schemas.py`, `models.py`, `swagger_schemas.py` | Scan `type` hard-coded to `["user"]`; examples refer to users | Deals scans rejected by validation | `["deals"]` |
| 13 | 🟡 | `utils.build_dataset_name` | Prefix hard-coded `hubspot_users`, no sanitising of the org ID | Wrong schema names; odd characters break SQL identifiers | Prefix `hubspot_deals`, sanitise to `[a-z0-9_]` |
| 14 | 🟡 | `api/routes.py` results | `tableName` defaults to `users` | Results endpoint 404s without an explicit `tableName` | Default `hubspot_deals` |
| 15 | 🟡 | `.gitignore` | Generated empty | `.env` with real secrets would be committed | Proper `.gitignore` (`.env*` except `.env.example`, `.dlt/`, logs) |
| 16 | 🟡 | `docker-compose.yml` | `HUBSPOT_DEALS_API_*` env vars are not read by any code | HubSpot settings cannot be configured | Replaced with the `HUBSPOT_*` vars read by `config.py` |
| 17 | 🟡 | Template `services/api_service.py` | Placeholder endpoints (`/v1/data`, `/v1/me`), no timeout on requests, single 429 retry | Not usable as-is | Replaced by `services/hubspot_api_service.py` (template file removed) |
| 18 | ⚪ | Health checks | Only `/api/health`; the task and the guidelines use `/health`. Docker healthchecks pointed at `/api/health` | – | Added root `/health` (DB check, 200/503); healthchecks use it |
| 19 | ⚪ | `config.API_DOCS_PATH='/docs'` | Swagger served at `/docs`; `/docs/` (as in the task) depends on redirect behaviour | – | `'/docs/'` |
| 20 | ⚪ | Generator `README.md` | Documents endpoints under `/api/v1/...`; generated code mounts them at `/api` | Confusing | Documented the real paths |
| 21 | ⚪ | Generated `.env.example` | Values for a different service (`hubspot_users`, port 5000) | – | Rewritten for this service |
| 22 | ⚪ | Template docs | `APi-DOCS.md` describes a CSV/Excel download endpoint that the template does not implement | – | Documented as not available |
| 23 | ⚪ | Security | No inbound authentication on the API | Anyone who can reach the port can start scans | Optional `SERVICE_API_KEY` → `X-API-Key` (exposed in Swagger "Authorize") |

## Environment note (not a generator issue)
The first `docker compose up --build` on the test machine failed with `unauthorized: personal access token is expired`. The local Docker Hub login had expired, and Docker sends stored credentials even for public images. The fix is `docker logout` or a fresh `docker login`. For this run the images were pulled anonymously with a temporary empty `DOCKER_CONFIG`.

## Spec vs. HubSpot reality
- **Rate limit**: the task says 150 requests / 10 s. HubSpot's current published burst limits for private apps are 100 / 10 s (Free and Starter) and 190 / 10 s (Professional and Enterprise). The limiter defaults to 150 as specified, is configurable, and 429s are retried with `Retry-After` either way.
- **Private apps** are now labelled *legacy private apps* in HubSpot; the creation steps in Task 2.1 still apply.
