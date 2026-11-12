# E2E test report - mock

Run: 2026-11-08 13:50:49 UTC  
Result: **25/25 checks passed**

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | GET /health returns 200 healthy | PASS | 200 in 39.7 ms |
| 2 | GET /api/health returns 200 healthy | PASS | 200 in 64.2 ms |
| 3 | Swagger UI at /docs/ reachable | PASS | 200 in 16.5 ms |
| 4 | OpenAPI spec lists scan endpoints | PASS | 16 paths |
| 5 | Access token valid with crm.objects.deals.read | PASS | 200; portalId=12345678 accountType=DEVELOPER_TEST |
| 6 | Invalid token rejected with 401 | PASS | 401 |
| 7 | POST /api/scan/start accepted (202) | PASS | 202 in 169.5 ms |
| 8 | Duplicate scanId rejected (409) | PASS | 409 |
| 9 | Scan completed | PASS | status=completed in ~4.1s; error=None |
| 10 | recordsExtracted >= 5 | PASS | 5 |
| 11 | Results tables include hubspot_deals | PASS | ['hubspot_deals'] |
| 12 | Results API returns deals | PASS | 5 rows in 211.2 ms |
| 13 | Access token stored encrypted (not plaintext) in job config | PASS | auth is an encrypted blob |
| 14 | Postgres hubspot_deals_acme_mock.hubspot_deals has >= 5 rows | PASS | 5 |
| 15 | No duplicate (_tenant_id, id) rows | PASS | 0 duplicates |
| 16 | Typed columns: amount numeric, closedate timestamptz, hs_is_closed_won boolean | PASS | amount=numeric, closedate=timestamp with time zone |
| 17 | ETL metadata columns present (_extracted_at, _scan_id, _tenant_id) | PASS |  |
| 18 | Metadata populated on every row | PASS | 0 rows with NULL metadata |
| 19 | Performance indexes created (tenant/stage/dates + unique merge key) | PASS | 9 indexes |
| 20 | Scan paused mid-extraction with a resumable checkpoint | PASS | phase=main_data_paused page=2 records=2 |
| 21 | POST /resume accepted (202) | PASS | 202 |
| 22 | Resumed scan completed with all deals | PASS | status=completed records=5 |
| 23 | No duplicates after pause/resume | PASS | 0 duplicates |
| 24 | Service healthy again after container restart | PASS |  |
| 25 | Scan history persists across restart | PASS |  |

## Deals in Postgres

| id | dealname | amount | dealstage | closedate | dealtype |
|---|---|---|---|---|---|
| 40000000001 | Acme Corp - Starter Plan | 5000.00 | qualifiedtobuy | 2026-12-08 17:00:00+00 | newbusiness |
| 40000000002 | Globex - Analytics Add-on | 25000.00 | presentationscheduled | 2026-12-23 17:00:00+00 | existingbusiness |
| 40000000003 | Initech - Enterprise Migration | 50000.00 | closedwon | 2026-10-29 17:00:00+00 | newbusiness |
| 40000000004 | Umbrella Health - Data Platform | 75000.00 | closedlost | 2026-10-19 17:00:00+00 | newbusiness |
| 40000000005 | Stark Industries - Global Rollout | 100000.00 | contractsent | 2027-01-07 17:00:00+00 | newbusiness |

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
| 5 | main_data | 1 | 1 | 1 |
| 6 | main_data | 2 | 2 | 2 |
| 7 | main_data_paused | 2 | 2 | 2 |
| 8 | main_data | 3 | 3 | 3 |
| 9 | main_data | 4 | 4 | 4 |
| 10 | main_data_completed | 5 | 5 |
