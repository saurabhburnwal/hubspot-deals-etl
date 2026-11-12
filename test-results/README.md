# Test results

| File | What it shows | Status |
|---|---|---|
| [GENERATOR-ISSUES.md](GENERATOR-ISSUES.md) | Issues and deviations found in the DLT Generator output, and how each was fixed | ✅ |
| [docker-build.log](docker-build.log) | Clean `docker compose up -d --build` from scratch (`down -v` first), exit 0 | ✅ |
| [health-check.txt](health-check.txt) | `/health`, `/api/health` and `/docs/` responses; container status | ✅ |
| [unit-tests.log](unit-tests.log) | 12/12 unit tests (HubSpot client, rate limiter, transforms, checkpoint pause/resume) | ✅ |
| [e2e-mock.md](e2e-mock.md) / [.json](e2e-mock.json) | 25/25 end-to-end checks through the real service, Postgres and dlt, with HubSpot replaced by `tests/mock_hubspot.py` | ✅ |
| [test-deals.json](test-deals.json) | IDs and values of the 5 test deals created in HubSpot test portal 247974551 | ✅ |
| [e2e-hubspot.md](e2e-hubspot.md) / [.json](e2e-hubspot.json) | 26/26 end-to-end checks against **real HubSpot**: health, docs, auth, scan, 5/5 recorded deal IDs in Postgres, types, indexes, pause/resume, restart | ✅ |
| [db-verification.md](db-verification.md) | Field-by-field comparison of the 5 seeded deals with the rows in Postgres: 5/5 match on all 10 fields | ✅ |
| [deal-properties.md](deal-properties.md) / [.json](deal-properties.json), [deal-pipelines.json](deal-pipelines.json) | All 208 deal properties and the pipeline stages in the test portal | ✅ |

## Reproducing the HubSpot results
```bash
# token in .env as HUBSPOT_ACCESS_TOKEN=pat-... (git-ignored)
python3 scripts/seed_test_deals.py            # -> test-deals.json
python3 scripts/export_deal_properties.py     # -> deal-properties.*
HUBSPOT_TEST_DELAY_SECONDS=2 HUBSPOT_CHECKPOINT_INTERVAL=1 docker compose up -d hubspot_deals_service_dev
python3 scripts/e2e_test.py --label hubspot   # -> e2e-hubspot.*
docker compose up -d hubspot_deals_service_dev
```

The E2E report never contains the access token. The JSON evidence holds only the portal ID, account type and rate-limit headers.
