# E2E test report - hubspot

Run: 2026-11-12 02:46:10 UTC  
Result: **26/26 checks passed**

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | GET /health returns 200 healthy | PASS | 200 in 39.4 ms |
| 2 | GET /api/health returns 200 healthy | PASS | 200 in 82.1 ms |
| 3 | Swagger UI at /docs/ reachable | PASS | 200 in 19.5 ms |
| 4 | OpenAPI spec lists scan endpoints | PASS | 16 paths |
| 5 | Access token valid with crm.objects.deals.read | PASS | 200; portalId=247974551 accountType=DEVELOPER_TEST |
| 6 | Invalid token rejected with 401 | PASS | 401 |
| 7 | POST /api/scan/start accepted (202) | PASS | 202 in 194.0 ms |
| 8 | Duplicate scanId rejected (409) | PASS | 409 |
| 9 | Scan completed | PASS | status=completed in ~9.1s; error=None |
| 10 | recordsExtracted >= 5 | PASS | 5 |
| 11 | Results tables include hubspot_deals | PASS | ['hubspot_deals'] |
| 12 | Results API returns deals | PASS | 5 rows in 82.2 ms |
| 13 | Access token stored encrypted (not plaintext) in job config | PASS | auth is an encrypted blob |
| 14 | Postgres hubspot_deals_e2e_hubspot.hubspot_deals has >= 5 rows | PASS | 5 |
| 15 | No duplicate (_tenant_id, id) rows | PASS | 0 duplicates |
| 16 | All recorded test deal IDs present in Postgres | PASS | 5/5 found |
| 17 | Typed columns: amount numeric, closedate timestamptz, hs_is_closed_won boolean | PASS | amount=numeric, closedate=timestamp with time zone |
| 18 | ETL metadata columns present (_extracted_at, _scan_id, _tenant_id) | PASS |  |
| 19 | Metadata populated on every row | PASS | 0 rows with NULL metadata |
| 20 | Performance indexes created (tenant/stage/dates + unique merge key) | PASS | 9 indexes |
| 21 | Scan paused mid-extraction with a resumable checkpoint | PASS | phase=main_data_paused page=2 records=2 |
| 22 | POST /resume accepted (202) | PASS | 202 |
| 23 | Resumed scan completed with all deals | PASS | status=completed records=5 |
| 24 | No duplicates after pause/resume | PASS | 0 duplicates |
| 25 | Service healthy again after container restart | PASS |  |
| 26 | Scan history persists across restart | PASS |  |

## Deals in Postgres

| id | dealname | amount | dealstage | closedate | dealtype |
|---|---|---|---|---|---|
| 366685469421 | [DLT TEST] Acme Corp - Starter Plan | 5000.00 | qualifiedtobuy | 2026-12-12 17:00:00+00 | newbusiness |
| 366685469419 | [DLT TEST] Globex - Analytics Add-on | 25000.00 | presentationscheduled | 2026-12-27 17:00:00+00 | existingbusiness |
| 366685469420 | [DLT TEST] Initech - Enterprise Migration | 50000.00 | closedwon | 2026-11-02 17:00:00+00 | newbusiness |
| 366685469418 | [DLT TEST] Umbrella Health - Data Platform | 75000.00 | closedlost | 2026-10-23 17:00:00+00 | newbusiness |
| 366685469417 | [DLT TEST] Stark Industries - Global Rollout | 100000.00 | contractsent | 2027-01-11 17:00:00+00 | newbusiness |

## Table columns (information_schema)

| column | type | nullable |
|---|---|---|
| id | character varying | NO |
| _tenant_id | character varying | NO |
| dealname | character varying | YES |
| amount | numeric | YES |
| dealstage | character varying | YES |
| pipeline | character varying | YES |
| closedate | timestamp with time zone | YES |
| createdate | timestamp with time zone | YES |
| hs_lastmodifieddate | timestamp with time zone | YES |
| dealtype | character varying | YES |
| description | character varying | YES |
| hubspot_owner_id | character varying | YES |
| hs_priority | character varying | YES |
| deal_currency_code | character varying | YES |
| amount_in_home_currency | numeric | YES |
| hs_deal_stage_probability | numeric | YES |
| hs_forecast_amount | numeric | YES |
| hs_forecast_probability | numeric | YES |
| hs_projected_amount | numeric | YES |
| hs_closed_amount | numeric | YES |
| hs_is_closed | boolean | YES |
| hs_is_closed_won | boolean | YES |
| days_to_close | bigint | YES |
| hs_next_step | character varying | YES |
| closed_lost_reason | character varying | YES |
| closed_won_reason | character varying | YES |
| hs_analytics_source | character varying | YES |
| num_associated_contacts | bigint | YES |
| num_contacted_notes | bigint | YES |
| num_notes | bigint | YES |
| notes_last_updated | timestamp with time zone | YES |
| hs_object_id | bigint | YES |
| created_at | timestamp with time zone | YES |
| updated_at | timestamp with time zone | YES |
| archived | boolean | YES |
| archived_at | timestamp with time zone | YES |
| _scan_id | character varying | NO |
| _extracted_at | timestamp with time zone | NO |
| _page_number | bigint | YES |
| _source_service | character varying | YES |
| _dlt_load_id | character varying | NO |
| _dlt_id | character varying | NO |

## Indexes

- `hubspot_deals__dlt_id_key`
- `idx_hubspot_deals_open_closedate`
- `idx_hubspot_deals_pipeline_stage`
- `idx_hubspot_deals_scan`
- `idx_hubspot_deals_tenant_closedate`
- `idx_hubspot_deals_tenant_createdate`
- `idx_hubspot_deals_tenant_modified`
- `idx_hubspot_deals_tenant_stage`
- `uq_hubspot_deals_tenant_id`

## Checkpoint trail (pause/resume scan)

| id | phase | page | records | cursor |
|---|---|---|---|---|
| 12 | main_data | 1 | 1 | 366685469418 |
| 13 | main_data | 2 | 2 | 366685469419 |
| 14 | main_data_paused | 2 | 2 | 366685469419 |
| 15 | main_data | 3 | 3 | 366685469420 |
| 16 | main_data | 4 | 4 | 366685469421 |
| 17 | main_data_completed | 5 | 5 |
