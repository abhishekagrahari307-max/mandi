import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_dashboard_snapshot as builder  # noqa: E402


class BrowserSnapshotTests(unittest.TestCase):
    def test_compact_snapshot_exactly_reproduces_canonical_rows(self):
        snapshot = json.loads((ROOT / "data/dashboard.json").read_text(encoding="utf-8"))
        self.assertEqual(snapshot["schema_version"], 1)
        latest = json.loads((ROOT / "data/latest.json").read_text(encoding="utf-8"))
        sources = json.loads((ROOT / "data/source_prices.json").read_text(encoding="utf-8"))
        expected_rows = len(latest.get("records") or [])
        expected_rows += sum(len(feed.get("records") or []) for feed in sources.get("feeds") or [])
        self.assertEqual(builder.verify_snapshot(snapshot), expected_rows)

    def test_compact_snapshot_is_small_and_has_no_raw_record_arrays(self):
        path = ROOT / "data/dashboard.json"
        self.assertLess(path.stat().st_size, 2_000_000)
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        self.assertNotIn("records", snapshot["latest"])
        for feed in snapshot["source_prices"]["feeds"]:
            self.assertNotIn("records", feed)
            self.assertIn("entries", feed)

    def test_dashboard_uses_compact_snapshot_and_bounded_dom(self):
        index = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("fetchJson('data/dashboard.json', null)", index)
        self.assertIn("const RATES_PAGE_SIZE = 100", index)
        self.assertIn("visibleRecords.forEach(r => {", index)
        self.assertIn("function showMoreRates()", index)
        self.assertIn("const RANKING_PAGE_SIZE = 100", index)
        self.assertIn("records.slice(0, RANKING_PAGE_SIZE)", index)
        self.assertIn("recs.slice(0, DISTRICT_DETAIL_LIMIT).map", index)
        self.assertIn("filtered.slice(0, SOURCE_FEED_RENDER_LIMIT)", index)
        self.assertIn("function nowInIstParts()", index)
        self.assertNotIn("fetch(`data/latest.json?t=${timestamp}`)", index)
        self.assertNotIn("fetchJson('data/source_prices.json'", index)
        self.assertNotIn("window.location.reload(true)", index)
        self.assertNotIn("setInterval(fetchDashboardData, 120000)", index)

    def test_service_worker_avoids_large_and_timestamped_cache_entries(self):
        worker = (ROOT / "sw.js").read_text(encoding="utf-8")
        self.assertIn("const CACHE_NAME = 'up-mandi-v22'", worker)
        self.assertIn("./data/dashboard.json", worker)
        self.assertIn("function stableCacheRequest", worker)
        self.assertIn("MAX_CACHEABLE_BYTES", worker)
        self.assertNotIn("'./data/latest.json'", worker)
        self.assertNotIn("'./data/source_prices.json'", worker)

    def test_update_workflow_builds_and_commits_browser_snapshot(self):
        workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
        self.assertIn("python scripts/build_dashboard_snapshot.py --verify", workflow)
        self.assertIn("data/dashboard.json", workflow)
        self.assertIn("Refresh official government data", workflow)


if __name__ == "__main__":
    unittest.main()
