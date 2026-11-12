#!/usr/bin/env python3
"""
Export every deal property defined in the HubSpot portal (GET
/crm/v3/properties/deals) and the deal pipelines/stages to test-results/.

Usage:
    HUBSPOT_ACCESS_TOKEN=pat-... python scripts/export_deal_properties.py
"""

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from seed_test_deals import HubSpotHTTP, load_token  # noqa: E402


def main() -> None:
    http = HubSpotHTTP(load_token())

    status, body = http.request("GET", "/crm/v3/properties/deals")
    if status != 200:
        sys.exit(f"Properties request failed ({status}): {body.get('message')}")
    props = sorted(body.get("results", []), key=lambda p: (p.get("groupName", ""), p["name"]))
    slim = [{k: p.get(k) for k in ("name", "label", "type", "fieldType", "groupName", "hubspotDefined",
                                   "calculated", "description")} for p in props]

    status, body = http.request("GET", "/crm/v3/pipelines/deals")
    pipelines = body.get("results", []) if status == 200 else []

    out_dir = ROOT / "test-results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "deal-properties.json").write_text(json.dumps(slim, indent=2))
    (out_dir / "deal-pipelines.json").write_text(json.dumps(pipelines, indent=2))

    lines = ["# HubSpot deal properties (exported from the test portal)", "",
             f"Total: {len(slim)} properties - by type: "
             + ", ".join(f"{t}={n}" for t, n in Counter(p['type'] for p in slim).most_common()), "",
             "| name | label | type | fieldType | group | HubSpot-defined |", "|---|---|---|---|---|---|"]
    for p in slim:
        lines.append(f"| `{p['name']}` | {(p['label'] or '').replace('|', '/')} | {p['type']} | "
                     f"{p['fieldType']} | {p['groupName']} | {p['hubspotDefined']} |")
    lines += ["", "## Pipelines and stages", ""]
    for pl in pipelines:
        lines.append(f"### {pl.get('label')} (`{pl.get('id')}`)")
        lines += ["", "| stage id | label | probability | closed |", "|---|---|---|---|"]
        for st in sorted(pl.get("stages", []), key=lambda x: x.get("displayOrder", 0)):
            md = st.get("metadata") or {}
            lines.append(f"| `{st['id']}` | {st['label']} | {md.get('probability')} | {md.get('isClosed')} |")
        lines.append("")
    (out_dir / "deal-properties.md").write_text("\n".join(lines) + "\n")
    print(f"Exported {len(slim)} properties and {len(pipelines)} pipelines to test-results/")


if __name__ == "__main__":
    main()
