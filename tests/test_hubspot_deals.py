"""
Unit tests for the HubSpot API service and the deals DLT data source.
Run inside the service container (all deps installed):

    docker exec hubspot_deals_service_dev python -m unittest discover -s tests -v
"""

import os
import sys
import time
import unittest
from datetime import datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LOKI_ENABLED", "false")

from config import get_config  # noqa: E402
from services import data_source as ds  # noqa: E402
from services.hubspot_api_service import (  # noqa: E402
    HubSpotAPIService,
    HubSpotAuthenticationError,
    SlidingWindowRateLimiter,
)
from tests.mock_hubspot import NOSCOPE, VALID, MockHubSpot  # noqa: E402


class HubSpotAPIServiceTests(unittest.TestCase):
    def setUp(self):
        self.mock = MockHubSpot(deal_count=5).start()
        self.api = HubSpotAPIService(base_url=self.mock.base_url, retry_backoff_seconds=0.1)

    def tearDown(self):
        self.mock.stop()

    def test_get_deals_single_page_and_params(self):
        page = self.api.get_deals(VALID, limit=100, properties=["dealname", "amount"])
        self.assertEqual(len(page["results"]), 5)
        self.assertIsNone(self.api.next_cursor(page))
        _, q = self.mock.requests[-1]
        self.assertEqual(q["properties"], "dealname,amount")
        self.assertEqual(q["archived"], "false")
        self.assertEqual(q["limit"], "100")

    def test_limit_is_capped_at_100(self):
        self.api.get_deals(VALID, limit=500)
        self.assertEqual(self.mock.requests[-1][1]["limit"], "100")

    def test_cursor_pagination_iterates_all_pages(self):
        deals = list(self.api.iter_deals(VALID, page_size=2))
        self.assertEqual(len(deals), 5)
        self.assertEqual(len({d["id"] for d in deals}), 5)
        afters = [q.get("after") for p, q in self.mock.requests if p == "/crm/v3/objects/deals"]
        self.assertEqual(afters, [None, "2", "4"])

    def test_invalid_token_raises_auth_error(self):
        with self.assertRaises(HubSpotAuthenticationError) as ctx:
            self.api.get_deals("pat-bad-token-123")
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.category, "INVALID_AUTHENTICATION")

    def test_validate_credentials(self):
        self.assertEqual(self.api.validate_credentials(VALID)["has_deals_scope"], True)
        noscope = self.api.validate_credentials(NOSCOPE)
        self.assertTrue(noscope["valid"])
        self.assertFalse(noscope["has_deals_scope"])
        bad = self.api.validate_credentials("pat-bad-token-123")
        self.assertFalse(bad["valid"])

    def test_429_is_retried_with_retry_after(self):
        self.mock.rate_limit_every = 2  # every 2nd deals request is rate limited
        start = time.monotonic()
        deals = list(self.api.iter_deals(VALID, page_size=2))
        self.assertEqual(len(deals), 5)
        self.assertGreaterEqual(time.monotonic() - start, 1.0)  # honoured Retry-After: 1

    def test_rate_limit_headers_captured(self):
        self.api.get_deals(VALID)
        usage = self.api.get_api_usage()
        self.assertEqual(usage["interval_max"], 150)
        self.assertEqual(usage["daily_limit"], 250000)


class RateLimiterTests(unittest.TestCase):
    def test_sliding_window_blocks_when_full(self):
        limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=0.5)
        start = time.monotonic()
        for _ in range(4):
            limiter.acquire()
        self.assertGreaterEqual(time.monotonic() - start, 0.45)


class TransformTests(unittest.TestCase):
    def test_transform_types_and_metadata(self):
        record = {
            "id": "123",
            "properties": {
                "dealname": "X", "amount": "25000.50", "closedate": "2026-12-31T17:00:00Z",
                "hs_is_closed_won": "true", "hs_object_id": "123", "days_to_close": "30",
                "hs_deal_stage_probability": "0.4", "description": "", "notes_last_updated": "1700000000000",
            },
            "createdAt": "2026-11-08T10:00:00.000Z", "updatedAt": "2026-11-08T10:05:00.000Z",
            "archived": False,
        }
        now = datetime(2026, 11, 8)
        row = ds.transform_deal(record, ds.STATIC_PROPERTY_TYPES, "org-1", "scan-1", 1, now)
        self.assertEqual(row["id"], "123")
        self.assertEqual(row["amount"], Decimal("25000.50"))
        self.assertEqual(row["closedate"].isoformat(), "2026-12-31T17:00:00+00:00")
        self.assertIs(row["hs_is_closed_won"], True)
        self.assertEqual(row["hs_object_id"], 123)
        self.assertEqual(row["days_to_close"], 30)
        self.assertEqual(row["hs_deal_stage_probability"], Decimal("0.4"))
        self.assertIsNone(row["description"])  # empty string -> NULL
        self.assertEqual(row["notes_last_updated"].year, 2023)  # epoch ms handled
        self.assertEqual(row["created_at"].isoformat(), "2026-11-08T10:00:00+00:00")
        self.assertEqual((row["_tenant_id"], row["_scan_id"], row["_page_number"]), ("org-1", "scan-1", 1))
        self.assertEqual(row["_extracted_at"], now)


class DataSourceTests(unittest.TestCase):
    def setUp(self):
        self.mock = MockHubSpot(deal_count=5).start()
        self.cfg = get_config()
        self._saved = (self.cfg.HUBSPOT_API_BASE_URL, self.cfg.HUBSPOT_CHECKPOINT_INTERVAL,
                       self.cfg.HUBSPOT_TEST_DELAY_SECONDS)
        self.cfg.HUBSPOT_API_BASE_URL = self.mock.base_url
        self.cfg.HUBSPOT_CHECKPOINT_INTERVAL = 2
        self.cfg.HUBSPOT_TEST_DELAY_SECONDS = 0
        self.checkpoints = []

    def tearDown(self):
        (self.cfg.HUBSPOT_API_BASE_URL, self.cfg.HUBSPOT_CHECKPOINT_INTERVAL,
         self.cfg.HUBSPOT_TEST_DELAY_SECONDS) = self._saved
        self.mock.stop()

    def _source(self, pause_after_pages=None, resume_from=None):
        pages_seen = {"n": 0}

        def on_checkpoint(job_id, cp):
            self.checkpoints.append(cp)

        def pause_cb(job_id):
            if pause_after_pages is None:
                return False
            pages_seen["n"] += 1
            return pages_seen["n"] > pause_after_pages

        [resource] = ds.create_data_source(
            job_config={"organizationId": "org-test", "scanId": "scan-test"},
            auth_config={"accessToken": VALID},
            filters={"scan_id": "scan-test", "batchSize": 1},
            checkpoint_callback=on_checkpoint,
            check_cancel_callback=lambda j: False,
            check_pause_callback=pause_cb,
            resume_from=resume_from,
        )
        return resource

    def test_extracts_all_deals_with_periodic_checkpoints(self):
        rows = list(self._source())
        self.assertEqual(len(rows), 5)
        self.assertEqual(sorted(r["amount"] for r in rows),
                         [Decimal(x) for x in ("5000", "25000", "50000", "75000", "100000")])
        phases = [c["phase"] for c in self.checkpoints]
        self.assertEqual(phases, ["main_data", "main_data", "main_data_completed"])  # pages 2, 4, end
        self.assertEqual(self.checkpoints[-1]["records_processed"], 5)

    def test_pause_then_resume_is_lossless(self):
        first = list(self._source(pause_after_pages=2))
        self.assertEqual(len(first), 2)
        paused = self.checkpoints[-1]
        self.assertEqual(paused["phase"], "main_data_paused")
        self.assertEqual(paused["cursor"], "2")

        resume = {"cursor": paused["cursor"], "page_number": paused["page_number"],
                  "records_processed": paused["records_processed"]}
        second = list(self._source(resume_from=resume))
        self.assertEqual(len(second), 3)
        self.assertEqual({r["id"] for r in first} | {r["id"] for r in second},
                         {d["id"] for d in self.mock.deals})
        self.assertEqual(self.checkpoints[-1]["records_processed"], 5)

    def test_resource_hints(self):
        resource = self._source()
        self.assertEqual(resource.write_disposition, "merge")
        self.assertEqual(resource.name, "hubspot_deals")


if __name__ == "__main__":
    unittest.main(verbosity=2)
