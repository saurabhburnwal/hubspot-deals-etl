#!/usr/bin/env python3
"""
Minimal stdlib mock of the HubSpot CRM v3 endpoints used by this service.
Used by the unit tests and for offline end-to-end runs of the full pipeline
(point HUBSPOT_API_BASE_URL at it).

Endpoints:
    GET /crm/v3/objects/deals        limit/after/properties/archived, cursor paging
    GET /crm/v3/properties/deals     property metadata
    GET /crm/v3/pipelines/deals      default pipeline
    GET /account-info/v3/details     portal info
    POST /crm/v3/objects/deals/batch/create   (used by scripts/seed_test_deals.py)

Auth:  "Bearer pat-mock-valid"     -> full access
       "Bearer pat-mock-noscope"   -> 403 MISSING_SCOPES on deals
       anything else               -> 401

Env / ctor options:
    MOCK_DEAL_COUNT   number of deals (default 5, the assessment test deals)
    MOCK_429_EVERY    return 429 on every Nth deals request (default 0 = never)
"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

VALID = "pat-mock-valid"
NOSCOPE = "pat-mock-noscope"

BASE_DEALS = [
    ("Acme Corp - Starter Plan", "5000", "qualifiedtobuy", "newbusiness", "2026-12-08T17:00:00Z"),
    ("Globex - Analytics Add-on", "25000", "presentationscheduled", "existingbusiness", "2026-12-23T17:00:00Z"),
    ("Initech - Enterprise Migration", "50000", "closedwon", "newbusiness", "2026-10-29T17:00:00Z"),
    ("Umbrella Health - Data Platform", "75000", "closedlost", "newbusiness", "2026-10-19T17:00:00Z"),
    ("Stark Industries - Global Rollout", "100000", "contractsent", "newbusiness", "2027-01-07T17:00:00Z"),
]

PROPERTY_META = [
    {"name": "dealname", "type": "string"}, {"name": "amount", "type": "number"},
    {"name": "dealstage", "type": "enumeration"}, {"name": "pipeline", "type": "enumeration"},
    {"name": "closedate", "type": "datetime"}, {"name": "createdate", "type": "datetime"},
    {"name": "hs_lastmodifieddate", "type": "datetime"}, {"name": "dealtype", "type": "enumeration"},
    {"name": "description", "type": "string"}, {"name": "hs_is_closed", "type": "bool"},
    {"name": "hs_is_closed_won", "type": "bool"}, {"name": "hs_deal_stage_probability", "type": "number"},
    {"name": "hs_object_id", "type": "number"}, {"name": "hs_priority", "type": "enumeration"},
    {"name": "days_to_close", "type": "number"}, {"name": "hs_acv", "type": "number"},
]


def build_deals(count: int):
    deals = []
    for i in range(count):
        name, amount, stage, dtype, close = BASE_DEALS[i % len(BASE_DEALS)]
        deal_id = str(40000000000 + i + 1)
        closed = stage in ("closedwon", "closedlost")
        deals.append({
            "id": deal_id,
            "properties": {
                "dealname": name if i < len(BASE_DEALS) else f"{name} #{i + 1}",
                "amount": amount,
                "dealstage": stage,
                "pipeline": "default",
                "closedate": close,
                "createdate": "2026-11-08T10:00:00.000Z",
                "hs_lastmodifieddate": "2026-11-08T10:05:00.000Z",
                "dealtype": dtype,
                "description": f"Mock deal {i + 1}",
                "hs_is_closed": str(closed).lower(),
                "hs_is_closed_won": str(stage == "closedwon").lower(),
                "hs_deal_stage_probability": "1" if stage == "closedwon" else ("0" if closed else "0.4"),
                "hs_object_id": deal_id,
                "hs_priority": "high",
                "days_to_close": "30",
                "hs_acv": None,
            },
            "createdAt": "2026-11-08T10:00:00.000Z",
            "updatedAt": "2026-11-08T10:05:00.000Z",
            "archived": False,
        })
    return deals


class MockHubSpot:
    def __init__(self, host="127.0.0.1", port=0, deal_count=5, rate_limit_every=0):
        self.deals = build_deals(deal_count)
        self.rate_limit_every = rate_limit_every
        self.deal_requests = 0
        self.requests = []  # (path, query) log for assertions
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # quiet
                pass

            def _send(self, status, body, headers=None):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("X-HubSpot-RateLimit-Max", "150")
                self.send_header("X-HubSpot-RateLimit-Remaining", "149")
                self.send_header("X-HubSpot-RateLimit-Interval-Milliseconds", "10000")
                self.send_header("X-HubSpot-RateLimit-Daily", "250000")
                self.send_header("X-HubSpot-RateLimit-Daily-Remaining", "249000")
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                url = urlparse(self.path)
                q = {k: v[0] for k, v in parse_qs(url.query).items()}
                mock.requests.append((url.path, q))
                token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
                if token not in (VALID, NOSCOPE):
                    return self._send(401, {"status": "error", "category": "INVALID_AUTHENTICATION",
                                            "message": "Authentication credentials not found.",
                                            "correlationId": "mock-401"})
                if url.path == "/crm/v3/objects/deals":
                    if token == NOSCOPE:
                        return self._send(403, {"status": "error", "category": "MISSING_SCOPES",
                                                "message": "This app hasn't been granted all required scopes",
                                                "correlationId": "mock-403"})
                    mock.deal_requests += 1
                    if mock.rate_limit_every and mock.deal_requests % mock.rate_limit_every == 0:
                        return self._send(429, {"status": "error", "category": "RATE_LIMITS",
                                                "policyName": "TEN_SECONDLY_ROLLING",
                                                "message": "You have reached your ten_secondly_rolling limit."},
                                          {"Retry-After": "1"})
                    limit = min(int(q.get("limit", 10)), 100)
                    start = int(q.get("after", 0))
                    wanted = q.get("properties", "").split(",") if q.get("properties") else None
                    page = []
                    for d in mock.deals[start:start + limit]:
                        props = d["properties"]
                        if wanted:
                            props = {k: props.get(k) for k in wanted}
                        page.append({**d, "properties": props})
                    body = {"results": page}
                    nxt = start + limit
                    if nxt < len(mock.deals):
                        body["paging"] = {"next": {"after": str(nxt), "link": f"?after={nxt}"}}
                    return self._send(200, body)
                if url.path == "/crm/v3/properties/deals":
                    return self._send(200, {"results": PROPERTY_META})
                if url.path == "/crm/v3/pipelines/deals":
                    return self._send(200, {"results": [{"id": "default", "label": "Sales Pipeline", "stages": []}]})
                if url.path == "/account-info/v3/details":
                    return self._send(200, {"portalId": 12345678, "accountType": "DEVELOPER_TEST",
                                            "timeZone": "US/Eastern", "companyCurrency": "USD"})
                return self._send(404, {"status": "error", "message": "Not found", "category": "OBJECT_NOT_FOUND"})

            def do_POST(self):
                url = urlparse(self.path)
                token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
                if token != VALID:
                    return self._send(401, {"status": "error", "category": "INVALID_AUTHENTICATION",
                                            "message": "Authentication credentials not found."})
                if url.path != "/crm/v3/objects/deals/batch/create":
                    return self._send(404, {"status": "error", "message": "Not found"})
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                created = []
                for item in body.get("inputs", []):
                    deal_id = str(40000000000 + len(mock.deals) + 1)
                    deal = {"id": deal_id, "properties": {**item["properties"], "hs_object_id": deal_id},
                            "createdAt": "2026-11-08T10:00:00.000Z", "updatedAt": "2026-11-08T10:00:00.000Z",
                            "archived": False}
                    mock.deals.append(deal)
                    created.append(deal)
                return self._send(201, {"status": "COMPLETE", "results": created})

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.port = self.server.server_address[1]
        self.base_url = f"http://{host}:{self.port}"

    def start(self):
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def stop(self):
        self.server.shutdown()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
    m = MockHubSpot("0.0.0.0", port, int(os.environ.get("MOCK_DEAL_COUNT", 5)),
                    int(os.environ.get("MOCK_429_EVERY", 0)))
    print(f"Mock HubSpot listening on {m.base_url}", flush=True)
    m.server.serve_forever()
