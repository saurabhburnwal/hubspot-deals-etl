# HubSpot Setup (Phase 2)

How the HubSpot developer account, test account, private app and test deals were set up. **The access token is never stored in this file or anywhere in the repository.**

## Account record

| Item | Value |
|---|---|
| Developer account | Saurabh |
| Test account | DLT Deal Test |
| Portal ID (Hub ID) | 247974551 |
| Account type | DEVELOPER_TEST |
| Data-centre region | na2 (token prefix `pat-na2-`) |
| Private app name | DLT Deals Extractor |
| Scopes | `crm.objects.deals.read` (+ `crm.objects.deals.write` only to run the seed script) |
| Token verified | 2026-11-12 via `POST /api/scan/validate-credentials`: 200, `has_deals_scope: true` |
| Token storage | Local `.env` only (git-ignored); passed to the service per scan request |
| Rate limits reported by HubSpot | 190 requests / 10 s, 1,000,000 / day (`X-HubSpot-RateLimit-*` headers) |
| Time zone / currency | US/Eastern / USD |

## Task 2.1 — Developer account and private app

1. Go to https://developers.hubspot.com/ and create a free developer account.
2. In the developer account go to **Development → Testing → Test Accounts → Create developer test account**, enter a name and click **Create**. It is a separate CRM portal with Enterprise trials of every Hub, so test data stays out of any real portal.
   - A test account expires after **90 days without API calls**. Renew it from the Test Accounts page, or just run a scan.
   - CLI alternative: `hs test-account create` (HubSpot CLI 8.3.0+).
3. Open the **test account** from the Test Accounts list (not the developer account itself), then go to ⚙️ **Settings → Integrations → Private Apps** and click **Create legacy app → Private**.
   - HubSpot now calls these **legacy private apps**, and the menu label differs between account versions. If *Private Apps* is not under Integrations, look for *Legacy apps* and create a **private** one. The scopes and token work the same way.
4. **Create a private app**:
   - *Basic info*: name **DLT Deals Extractor**.
   - *Scopes*: search `deals` and tick **`crm.objects.deals.read`**. Also tick `crm.objects.deals.write` if you want `scripts/seed_test_deals.py` to create the test deals; you can remove it afterwards.
   - **Create app**, then **Show token → Copy**.
5. Store the token safely:
   ```bash
   # in hubspot-deals-etl/.env  (git-ignored)
   HUBSPOT_ACCESS_TOKEN=pat-na1-...
   ```
6. Verify it:
   ```bash
   curl -s -X POST localhost:5200/api/scan/validate-credentials \
     -H 'Content-Type: application/json' -d "{\"accessToken\":\"$HUBSPOT_ACCESS_TOKEN\"}"
   # expect 200, has_deals_scope=true, and the portalId of the test account
   ```

If the token is ever exposed, use **Rotate** in the private app's *Auth* tab. The old token stops working immediately.

## Task 2.2 — Five test deals

| # | Deal | Amount | Stage (default pipeline) | Type | Priority | Close date |
|---|---|---|---|---|---|---|
| 1 | [DLT TEST] Acme Corp - Starter Plan | $5,000 | Qualified To Buy (`qualifiedtobuy`) | New business | low | +30 days |
| 2 | [DLT TEST] Globex - Analytics Add-on | $25,000 | Presentation Scheduled (`presentationscheduled`) | Existing business | medium | +45 days |
| 3 | [DLT TEST] Initech - Enterprise Migration | $50,000 | Closed Won (`closedwon`) | New business | high | -10 days |
| 4 | [DLT TEST] Umbrella Health - Data Platform | $75,000 | Closed Lost (`closedlost`), with a lost reason | New business | high | -20 days |
| 5 | [DLT TEST] Stark Industries - Global Rollout | $100,000 | Contract Sent (`contractsent`) | New business | high | +60 days |

This covers the four stages the task requires plus *Contract Sent*, all five required amounts, both deal types, three priorities, past and future close dates, and a description on every deal.

**Option A — script (recommended, records IDs automatically)**
```bash
HUBSPOT_ACCESS_TOKEN=pat-... python scripts/seed_test_deals.py
# prints the five deal IDs and writes test-results/test-deals.json
```
The script is idempotent: deals whose name already exists are not recreated.

**Option B — HubSpot UI**: *CRM → Deals → Create deal* five times with the values above, then copy each deal ID from the record URL (`.../record/0-3/<dealId>`) into `test-results/test-deals.json` in the format the script produces.

## Recorded deal IDs
Created 2026-11-12 with `scripts/seed_test_deals.py` (full values in [`test-results/test-deals.json`](../test-results/test-deals.json)):

| HubSpot deal ID | Deal | Amount | Stage |
|---|---|---|---|
| 366685469421 | [DLT TEST] Acme Corp - Starter Plan | $5,000 | qualifiedtobuy |
| 366685469419 | [DLT TEST] Globex - Analytics Add-on | $25,000 | presentationscheduled |
| 366685469420 | [DLT TEST] Initech - Enterprise Migration | $50,000 | closedwon |
| 366685469418 | [DLT TEST] Umbrella Health - Data Platform | $75,000 | closedlost |
| 366685469417 | [DLT TEST] Stark Industries - Global Rollout | $100,000 | contractsent |

All five were extracted and verified field-by-field in Postgres: see [`test-results/e2e-hubspot.md`](../test-results/e2e-hubspot.md) and [`test-results/db-verification.md`](../test-results/db-verification.md).
