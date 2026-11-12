#!/usr/bin/env python3
"""
End-to-end validation of the running hubspot-deals-etl service (Task 3.4).

Covers: health checks, Swagger docs, credential validation, full scan,
results API, Postgres verification (types, indexes, tenant isolation,
expected deal IDs), checkpoint pause/resume, and service restart.

Writes test-results/e2e-<label>.md (human report) and .json (raw evidence).
The access token is read from --token / HUBSPOT_ACCESS_TOKEN / .env and is
never written to the report.

Usage:
    python scripts/e2e_test.py --label hubspot            # real HubSpot
    python scripts/e2e_test.py --label mock --token pat-mock-valid --expected-count 5

For a reliable pause/resume test start the service with a per-request delay
and a checkpoint after every page (the test pauses once the first checkpoint
appears):
    HUBSPOT_TEST_DELAY_SECONDS=2 HUBSPOT_CHECKPOINT_INTERVAL=1 \
        docker compose up -d hubspot_deals_service_dev
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "test-results"
PG_CONTAINER = "hubspot_deals_postgres_dev"
SVC_CONTAINER = "hubspot_deals_service_dev"
DB = "hubspot_deals_data_dev"


# ------------------------------------------------------------------ helpers
def http(method, url, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            status = r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read().decode(), e.code
    ms = round((time.monotonic() - start) * 1000, 1)
    try:
        payload = json.loads(raw) if raw else None
    except ValueError:
        payload = raw[:200]
    return status, payload, ms


def psql(sql):
    out = subprocess.run(
        ["docker", "exec", PG_CONTAINER, "psql", "-U", "postgres", "-d", DB, "-At", "-F", "\t", "-c", sql],
        capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip())
    return [line.split("\t") for line in out.stdout.strip().splitlines() if line]


def load_token(cli_token):
    if cli_token:
        return cli_token
    token = os.environ.get("HUBSPOT_ACCESS_TOKEN", "")
    env = ROOT / ".env"
    if not token and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("HUBSPOT_ACCESS_TOKEN="):
                token = line.split("=", 1)[1].strip()
    if not token or "your-token-here" in token:
        sys.exit("No HubSpot token: pass --token or set HUBSPOT_ACCESS_TOKEN")
    return token


class Report:
    def __init__(self, label):
        self.label = label
        self.checks = []
        self.evidence = {}

    def check(self, name, ok, detail=""):
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""), flush=True)
        return ok

    def write(self):
        RESULTS.mkdir(exist_ok=True)
        passed = sum(c["ok"] for c in self.checks)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines = [f"# E2E test report - {self.label}", "", f"Run: {stamp}  ",
                 f"Result: **{passed}/{len(self.checks)} checks passed**", "",
                 "| # | Check | Result | Detail |", "|---|---|---|---|"]
        for i, c in enumerate(self.checks, 1):
            detail = str(c["detail"]).replace("|", "\\|")
            lines.append(f"| {i} | {c['name']} | {'PASS' if c['ok'] else 'FAIL'} | {detail} |")
        if "deal_rows" in self.evidence:
            lines += ["", "## Deals in Postgres", "", "| id | dealname | amount | dealstage | closedate | dealtype |",
                      "|---|---|---|---|---|---|"]
            for r in self.evidence["deal_rows"]:
                lines.append("| " + " | ".join(r) + " |")
        if "columns" in self.evidence:
            lines += ["", "## Table columns (information_schema)", "", "| column | type | nullable |", "|---|---|---|"]
            lines += [f"| {c} | {t} | {n} |" for c, t, n in self.evidence["columns"]]
        if "indexes" in self.evidence:
            lines += ["", "## Indexes", ""] + [f"- `{i}`" for i in self.evidence["indexes"]]
        if "checkpoints" in self.evidence:
            lines += ["", "## Checkpoint trail (pause/resume scan)", "",
                      "| id | phase | page | records | cursor |", "|---|---|---|---|---|"]
            lines += ["| " + " | ".join(r) + " |" for r in self.evidence["checkpoints"]]
        (RESULTS / f"e2e-{self.label}.md").write_text("\n".join(lines) + "\n")
        (RESULTS / f"e2e-{self.label}.json").write_text(
            json.dumps({"label": self.label, "run_at": stamp, "checks": self.checks, "evidence": self.evidence},
                       indent=2, default=str))
        print(f"\n{passed}/{len(self.checks)} passed -> test-results/e2e-{self.label}.md")
        return passed == len(self.checks)


def wait_status(base, scan_id, until, timeout=180):
    deadline = time.time() + timeout
    data = {}
    while time.time() < deadline:
        _, body, _ = http("GET", f"{base}/api/scan/{scan_id}/status")
        data = (body or {}).get("data") or {}
        if data.get("status") in until:
            return data
        time.sleep(1)
    return data


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:5200")
    ap.add_argument("--token")
    ap.add_argument("--label", default="hubspot")
    ap.add_argument("--org", default=None, help="tenant/organization id (default: e2e-<label>)")
    ap.add_argument("--expected-count", type=int, default=None,
                    help="expected deal count (default: number of deals in test-results/test-deals.json)")
    ap.add_argument("--skip-restart", action="store_true")
    args = ap.parse_args()

    token = load_token(args.token)
    base = args.base.rstrip("/")
    org = args.org or f"e2e-{args.label}"
    schema = "hubspot_deals_" + "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in org).lower()
    run = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    rep = Report(args.label)

    expected_ids = None
    seed_file = RESULTS / "test-deals.json"
    if seed_file.exists() and args.label != "mock":
        expected_ids = {d["id"] for d in json.loads(seed_file.read_text())["deals"]}
    expected_count = args.expected_count or (len(expected_ids) if expected_ids else 5)

    # 1. Health + docs
    st, body, ms = http("GET", f"{base}/health")
    rep.check("GET /health returns 200 healthy", st == 200 and body.get("status") == "healthy", f"{st} in {ms} ms")
    st, body, ms = http("GET", f"{base}/api/health")
    rep.check("GET /api/health returns 200 healthy", st == 200 and body.get("status") == "healthy", f"{st} in {ms} ms")
    st, _, ms = http("GET", f"{base}/docs/")
    rep.check("Swagger UI at /docs/ reachable", st == 200, f"{st} in {ms} ms")
    st, spec, _ = http("GET", f"{base}/api/swagger.json")
    paths = sorted((spec or {}).get("paths", {})) if isinstance(spec, dict) else []
    rep.check("OpenAPI spec lists scan endpoints", "/scan/start" in paths and "/scan/{scan_id}/resume" in paths,
              f"{len(paths)} paths")

    # 2. Credentials
    st, body, ms = http("POST", f"{base}/api/scan/validate-credentials", {"accessToken": token})
    data = (body or {}).get("data") or {}
    rep.check("Access token valid with crm.objects.deals.read", st == 200,
              f"{st}; portalId={data.get('portalId')} accountType={data.get('accountType')}")
    rep.evidence["account"] = {k: data.get(k) for k in ("portalId", "accountType", "timeZone", "companyCurrency")}
    rep.evidence["rate_limit_headers"] = data.get("rateLimit")
    st, _, _ = http("POST", f"{base}/api/scan/validate-credentials", {"accessToken": "pat-na1-invalid-token-000"})
    rep.check("Invalid token rejected with 401", st == 401, str(st))

    # 3. Full scan
    scan_id = f"e2e-{args.label}-{run}"
    req = {"config": {"scanId": scan_id, "organizationId": org, "type": ["deals"],
                      "auth": {"accessToken": token}, "filters": {}}}
    st, body, ms = http("POST", f"{base}/api/scan/start", req)
    rep.check("POST /api/scan/start accepted (202)", st == 202, f"{st} in {ms} ms")
    st, _, _ = http("POST", f"{base}/api/scan/start", req)
    rep.check("Duplicate scanId rejected (409)", st == 409, str(st))
    t0 = time.monotonic()
    final = wait_status(base, scan_id, {"completed", "failed", "cancelled"})
    took = round(time.monotonic() - t0, 1)
    rep.check("Scan completed", final.get("status") == "completed",
              f"status={final.get('status')} in ~{took}s; error={final.get('errorMessage')}")
    rep.check(f"recordsExtracted >= {expected_count}", (final.get("recordsExtracted") or 0) >= expected_count,
              str(final.get("recordsExtracted")))
    rep.evidence["scan_status"] = {k: final.get(k) for k in
                                   ("scanId", "status", "recordsExtracted", "duration", "startTime", "endTime",
                                    "metadata")}

    st, body, _ = http("GET", f"{base}/api/results/{scan_id}/tables")
    tables = [t.get("name") or t.get("tableName") for t in ((body or {}).get("data") or {}).get("tables", [])]
    rep.check("Results tables include hubspot_deals", "hubspot_deals" in tables, str(tables))
    st, body, ms = http("GET", f"{base}/api/results/{scan_id}/result?tableName=hubspot_deals&limit=100")
    results = ((body or {}).get("data") or {}).get("records", [])
    rep.check("Results API returns deals", st == 200 and len(results) >= expected_count,
              f"{len(results)} rows in {ms} ms")
    st, body, _ = http("GET", f"{base}/api/scan/{scan_id}/status")
    auth_stored = (((body or {}).get("data") or {}).get("config") or {}).get("auth")
    rep.check("Access token stored encrypted (not plaintext) in job config",
              isinstance(auth_stored, str) and token not in json.dumps(body), "auth is an encrypted blob")

    # 4. Database verification
    table = f'"{schema}"."hubspot_deals"'
    count = int(psql(f"select count(*) from {table}")[0][0])
    rep.check(f"Postgres {schema}.hubspot_deals has >= {expected_count} rows", count >= expected_count, str(count))
    dup = int(psql(f"select count(*) from (select _tenant_id, id from {table} group by 1,2 having count(*)>1) d")[0][0])
    rep.check("No duplicate (_tenant_id, id) rows", dup == 0, f"{dup} duplicates")
    if expected_ids:
        ids_in = {r[0] for r in psql(f"select id from {table}")}
        missing = expected_ids - ids_in
        rep.check("All recorded test deal IDs present in Postgres", not missing,
                  f"{len(expected_ids) - len(missing)}/{len(expected_ids)} found" + (f"; missing {missing}" if missing else ""))
        id_list = ",".join(f"'{i}'" for i in expected_ids)
        rows = psql(f"select id, dealname, amount, dealstage, closedate, coalesce(dealtype,'') from {table} "
                    f"where id in ({id_list}) order by amount")
    else:
        rows = psql(f"select id, dealname, amount, dealstage, closedate, coalesce(dealtype,'') from {table} "
                    f"order by amount limit 20")
    rep.evidence["deal_rows"] = rows
    cols = psql(f"select column_name, data_type, is_nullable from information_schema.columns "
                f"where table_schema='{schema}' and table_name='hubspot_deals' order by ordinal_position")
    rep.evidence["columns"] = cols
    coltypes = {c: t for c, t, _ in cols}
    rep.check("Typed columns: amount numeric, closedate timestamptz, hs_is_closed_won boolean",
              coltypes.get("amount") == "numeric" and coltypes.get("closedate") == "timestamp with time zone"
              and coltypes.get("hs_is_closed_won") == "boolean",
              f"amount={coltypes.get('amount')}, closedate={coltypes.get('closedate')}")
    meta_ok = all(c in coltypes for c in ("_extracted_at", "_scan_id", "_tenant_id"))
    rep.check("ETL metadata columns present (_extracted_at, _scan_id, _tenant_id)", meta_ok)
    nulls = int(psql(f"select count(*) from {table} where _tenant_id is null or _scan_id is null "
                     f"or _extracted_at is null")[0][0])
    rep.check("Metadata populated on every row", nulls == 0, f"{nulls} rows with NULL metadata")
    idx = [r[0] for r in psql(f"select indexname from pg_indexes where schemaname='{schema}' "
                              f"and tablename='hubspot_deals' order by 1")]
    rep.evidence["indexes"] = idx
    rep.check("Performance indexes created (tenant/stage/dates + unique merge key)",
              {"uq_hubspot_deals_tenant_id", "idx_hubspot_deals_tenant_stage",
               "idx_hubspot_deals_tenant_closedate"} <= set(idx), f"{len(idx)} indexes")

    # 5. Checkpoint pause / resume (page size 1 => one page per deal)
    cp_scan = f"e2e-{args.label}-cp-{run}"
    cp_req = {"config": {"scanId": cp_scan, "organizationId": org, "type": ["deals"],
                         "auth": {"accessToken": token}, "filters": {"batchSize": 1}}}
    http("POST", f"{base}/api/scan/start", cp_req)
    paused_ok = False
    deadline = time.time() + 60
    while time.time() < deadline:  # pause after the first page is processed
        _, body, _ = http("GET", f"{base}/api/scan/{cp_scan}/status")
        d = (body or {}).get("data") or {}
        if d.get("status") == "running" and ((d.get("checkpointInfo") or {}).get("latestCheckpoint")):
            st, _, _ = http("POST", f"{base}/api/scan/{cp_scan}/pause")
            paused_ok = st == 200
            break
        if d.get("status") in ("completed", "failed"):
            break
        time.sleep(0.3)
    d = wait_status(base, cp_scan, {"paused", "completed", "failed"}, timeout=60)
    if paused_ok and d.get("status") == "paused":
        time.sleep(3)  # let the generator exit and dlt finish loading
        latest = (d.get("checkpointInfo") or {}).get("latestCheckpoint") or {}
        d = wait_status(base, cp_scan, {"paused"}, timeout=10)
        latest = (d.get("checkpointInfo") or {}).get("latestCheckpoint") or latest
        rep.check("Scan paused mid-extraction with a resumable checkpoint",
                  latest.get("phase") == "main_data_paused" and latest.get("cursor"),
                  f"phase={latest.get('phase')} page={latest.get('pageNumber')} "
                  f"records={latest.get('recordsProcessed')}")
        st, body, _ = http("POST", f"{base}/api/scan/{cp_scan}/resume")
        rep.check("POST /resume accepted (202)", st == 202, str(st))
        d = wait_status(base, cp_scan, {"completed", "failed"}, timeout=120)
        rep.check("Resumed scan completed with all deals", d.get("status") == "completed"
                  and (d.get("recordsExtracted") or 0) >= expected_count,
                  f"status={d.get('status')} records={d.get('recordsExtracted')}")
        dup = int(psql(f"select count(*) from (select _tenant_id, id from {table} group by 1,2 "
                       f"having count(*)>1) x")[0][0])
        rep.check("No duplicates after pause/resume", dup == 0, f"{dup} duplicates")
    else:
        rep.check("Scan paused mid-extraction with a resumable checkpoint", False,
                  f"could not pause in time (status={d.get('status')}); "
                  "restart with HUBSPOT_TEST_DELAY_SECONDS=2 HUBSPOT_CHECKPOINT_INTERVAL=1 for this test")
    rep.evidence["checkpoints"] = psql(
        f"select id, phase, \"pageNumber\", \"recordsProcessed\", coalesce(cursor,'') "
        f"from job_checkpoints where job_id='{cp_scan}' order by id")

    # 6. Restart resilience
    if not args.skip_restart:
        subprocess.run(["docker", "restart", SVC_CONTAINER], capture_output=True, check=False)
        up = False
        for _ in range(60):
            try:
                st, body, _ = http("GET", f"{base}/health", timeout=3)
                if st == 200:
                    up = True
                    break
            except Exception:
                pass
            time.sleep(1)
        rep.check("Service healthy again after container restart", up)
        st, body, _ = http("GET", f"{base}/api/scan/{scan_id}/status")
        rep.check("Scan history persists across restart",
                  st == 200 and ((body or {}).get("data") or {}).get("status") == "completed")

    sys.exit(0 if rep.write() else 1)


if __name__ == "__main__":
    main()
