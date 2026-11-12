#!/usr/bin/env python3
"""
Create the 5 HubSpot test deals required by the assessment (Task 2.2) and
record their IDs in test-results/test-deals.json.

Requires a private app token with crm.objects.deals.read AND
crm.objects.deals.write (write is only needed for this seeding script; the
extraction service itself only needs read).

Usage:
    HUBSPOT_ACCESS_TOKEN=pat-... python scripts/seed_test_deals.py
    # or put HUBSPOT_ACCESS_TOKEN in .env (git-ignored)

Idempotent: deals whose name already exists in the portal are not recreated;
their existing IDs are recorded instead.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import urllib.error
import urllib.parse
import urllib.request


class HubSpotHTTP:
    """Tiny stdlib HTTP client so the script needs no third-party packages."""

    def __init__(self, token: str):
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def request(self, method: str, path: str, params=None, body=None):
        url = f"{BASE}{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except ValueError:
                return e.code, {}

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "test-results" / "test-deals.json"
BASE = os.environ.get("HUBSPOT_API_BASE_URL", "https://api.hubapi.com")

# label (lowercase) -> default-pipeline stage id (fallback if pipeline lookup fails)
DEFAULT_STAGE_IDS = {
    "qualified to buy": "qualifiedtobuy",
    "presentation scheduled": "presentationscheduled",
    "contract sent": "contractsent",
    "closed won": "closedwon",
    "closed lost": "closedlost",
}


def load_token() -> str:
    token = os.environ.get("HUBSPOT_ACCESS_TOKEN", "")
    env_file = ROOT / ".env"
    if not token and env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("HUBSPOT_ACCESS_TOKEN="):
                token = line.split("=", 1)[1].strip()
    if not token or "your-token-here" in token:
        sys.exit("Set HUBSPOT_ACCESS_TOKEN (env var or .env) to a real private app token")
    return token


def days_from_now(days: int) -> str:
    d = datetime.now(timezone.utc).replace(hour=17, minute=0, second=0, microsecond=0) + timedelta(days=days)
    return d.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def test_deals(stage):
    """5 deals: varied stages, amounts ($5K-$100K), types, priorities, close dates."""
    return [
        {
            "dealname": "[DLT TEST] Acme Corp - Starter Plan",
            "amount": "5000",
            "dealstage": stage("qualified to buy"),
            "dealtype": "newbusiness",
            "hs_priority": "low",
            "closedate": days_from_now(30),
            "description": "Small team evaluating the starter plan. Qualified after discovery call; budget confirmed for Q1.",
        },
        {
            "dealname": "[DLT TEST] Globex - Analytics Add-on",
            "amount": "25000",
            "dealstage": stage("presentation scheduled"),
            "dealtype": "existingbusiness",
            "hs_priority": "medium",
            "closedate": days_from_now(45),
            "description": "Upsell of the analytics add-on to an existing customer. Product demo scheduled with their data team.",
        },
        {
            "dealname": "[DLT TEST] Initech - Enterprise Migration",
            "amount": "50000",
            "dealstage": stage("closed won"),
            "dealtype": "newbusiness",
            "hs_priority": "high",
            "closedate": days_from_now(-10),
            "description": "Enterprise migration project signed. 12-month contract with onboarding package.",
        },
        {
            "dealname": "[DLT TEST] Umbrella Health - Data Platform",
            "amount": "75000",
            "dealstage": stage("closed lost"),
            "dealtype": "newbusiness",
            "hs_priority": "high",
            "closedate": days_from_now(-20),
            "closed_lost_reason": "Chose a competitor with an on-premise deployment option.",
            "description": "Data platform RFP. Lost on deployment model requirements (on-prem only).",
        },
        {
            "dealname": "[DLT TEST] Stark Industries - Global Rollout",
            "amount": "100000",
            "dealstage": stage("contract sent"),
            "dealtype": "newbusiness",
            "hs_priority": "high",
            "closedate": days_from_now(60),
            "description": "Global rollout across 14 sites. Contract sent to procurement; legal review in progress.",
        },
    ]


def main() -> None:
    token = load_token()
    http = HubSpotHTTP(token)

    # Resolve stage IDs from the default pipeline (labels can differ per portal)
    stages = dict(DEFAULT_STAGE_IDS)
    status, body = http.request("GET", "/crm/v3/pipelines/deals")
    if status == 401:
        sys.exit(f"401 from HubSpot - token invalid: {body.get('message')}")
    if status == 200:
        pipelines = body.get("results", [])
        default = next((p for p in pipelines if p.get("id") == "default"), pipelines[0] if pipelines else None)
        if default:
            for st in default.get("stages", []):
                stages[st["label"].lower()] = st["id"]
    else:
        print(f"warn: pipeline lookup failed ({status}); using default stage ids")

    def stage(label: str) -> str:
        return stages.get(label, DEFAULT_STAGE_IDS[label])

    # Existing deals by name (idempotency)
    existing = {}
    after = None
    while True:
        params = {"limit": 100, "properties": "dealname"}
        if after:
            params["after"] = after
        status, body = http.request("GET", "/crm/v3/objects/deals", params=params)
        if status != 200:
            sys.exit(f"Listing deals failed ({status}): {body.get('message')}")
        for d in body.get("results", []):
            existing[d["properties"].get("dealname")] = d["id"]
        after = (body.get("paging") or {}).get("next", {}).get("after")
        if not after:
            break

    wanted = test_deals(stage)
    to_create = [d for d in wanted if d["dealname"] not in existing]
    created = {}
    if to_create:
        status, body = http.request(
            "POST", "/crm/v3/objects/deals/batch/create",
            body={"inputs": [{"properties": d} for d in to_create]},
        )
        if status == 403:
            sys.exit("403: token lacks crm.objects.deals.write - add the scope or create the deals in the UI")
        if status not in (200, 201):
            sys.exit(f"Creating deals failed ({status}): {body.get('message')}")
        for d in body.get("results", []):
            created[d["properties"]["dealname"]] = d["id"]

    records = []
    for d in wanted:
        deal_id = created.get(d["dealname"]) or existing.get(d["dealname"])
        records.append({"id": deal_id, "created_now": d["dealname"] in created, **d})
        print(f"{'created ' if d['dealname'] in created else 'existing'}  {deal_id:>14}  "
              f"${int(d['amount']):>7,}  {d['dealstage']:<24} {d['dealname']}")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                               "stage_ids": stages, "deals": records}, indent=2))
    print(f"\nRecorded {len(records)} deal IDs in {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
