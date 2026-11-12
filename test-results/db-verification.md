# Database verification - real HubSpot (portal 247974551)

Generated 2026-11-12 02:46 UTC by comparing `test-results/test-deals.json` (values sent to HubSpot by the seed script) with rows in `hubspot_deals_e2e_hubspot.hubspot_deals` after an extraction scan.

**Result: 5/5 deals match on every checked field** (dealname, amount, dealstage, dealtype, hs_priority, closedate, description, closed_lost_reason, pipeline, hs_is_closed/hs_is_closed_won).

| HubSpot ID | Deal | amount (NUMERIC) | dealstage | dealtype | priority | closedate | closed/won | stage prob. | Check |
|---|---|---|---|---|---|---|---|---|---|
| 366685469421 | Acme Corp - Starter Plan | 5,000.00 | qualifiedtobuy | newbusiness | low | 2026-12-12 | False/False | 0.4 | ✅ all 10 fields match |
| 366685469419 | Globex - Analytics Add-on | 25,000.00 | presentationscheduled | existingbusiness | medium | 2026-12-27 | False/False | 0.6 | ✅ all 10 fields match |
| 366685469420 | Initech - Enterprise Migration | 50,000.00 | closedwon | newbusiness | high | 2026-11-02 | True/True | 1.0 | ✅ all 10 fields match |
| 366685469418 | Umbrella Health - Data Platform | 75,000.00 | closedlost | newbusiness | high | 2026-10-23 | True/False | 0.0 | ✅ all 10 fields match |
| 366685469417 | Stark Industries - Global Rollout | 100,000.00 | contractsent | newbusiness | high | 2027-01-11 | False/False | 0.9 | ✅ all 10 fields match |

HubSpot computes `hs_is_closed`, `hs_is_closed_won` and `hs_deal_stage_probability` itself; they arrive as strings and are stored as BOOLEAN / NUMERIC(5,4).

## Aggregate by stage

```
dealstage       | count |   total   | tenant_ok 
-----------------------+-------+-----------+-----------
 qualifiedtobuy        |     1 |   5000.00 | t
 presentationscheduled |     1 |  25000.00 | t
 closedwon             |     1 |  50000.00 | t
 closedlost            |     1 |  75000.00 | t
 contractsent          |     1 | 100000.00 | t
(5 rows)
```

## Tenant isolation (one schema per organizationId)

```
table_schema        | count 
---------------------------+-------
 hubspot_deals_acme_mock   |     1
 hubspot_deals_e2e_hubspot |     1
(2 rows)
```

Each tenant's deals live in their own `hubspot_deals_<org>` schema. The mock-HubSpot test tenant (`hubspot_deals_acme_mock`) never touched the real-HubSpot tenant schema `hubspot_deals_e2e_hubspot`.
