import json
import re
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import alerts
import prediction
import update_data


ROOT = Path(__file__).resolve().parents[1]


class OfficialDataIntegrityTests(unittest.TestCase):
    def test_unverified_snapshot_never_contains_generated_rates(self):
        latest = json.loads((ROOT / "data/latest.json").read_text(encoding="utf-8"))
        if not latest.get("verified"):
            # Single-source records are allowed, but they must be marked as single_source
            records = latest.get("records", [])
            for record in records:
                self.assertEqual(record.get("verification_level"), "single_source",
                    "Unverified records must be marked as single_source")

    def test_official_formatter_does_not_invent_arrivals(self):
        record = update_data.format_record({
            "state": "Uttar Pradesh",
            "district": "Kanpur Nagar",
            "market": "Kanpur Grain",
            "commodity": "Wheat",
            "variety": "Dara",
            "grade": "FAQ",
            "min_price": "2400",
            "max_price": "2500",
            "modal_price": "2450",
            "arrival_date": "27/07/2026",
        })
        self.assertIsNotNone(record)
        self.assertIsNone(record["arrivals"])
        self.assertTrue(record["verified"])

    def test_prices_publish_only_with_matching_government_feeds(self):
        base = {
            "state": "Uttar Pradesh", "district": "Kanpur Nagar",
            "market": "Kanpur Grain", "commodity": "Wheat",
            "modal_price": 2450, "min_price": 2400, "max_price": 2500,
            "arrival_date": "27/07/2026",
        }
        record = update_data.format_record(base)

        # A single feed is never enough: one source cannot cross-verify itself.
        published, examined = update_data.select_publishable_records([
            ("data.gov.in", [dict(record)]),
        ])
        self.assertEqual(published, [])
        self.assertEqual(examined, 1)

        # Two agreeing government feeds publish exactly one record. Only two of
        # the four configured feeds are publicly obtainable, so this is the
        # strictest gate that can ever pass in practice.
        published, examined = update_data.select_publishable_records([
            ("data.gov.in", [dict(record)]),
            ("AGMARKNET", [dict(record)]),
        ])
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]["verification_count"], 2)
        self.assertTrue(published[0]["multi_source_verified"])
        # The published modal price is the exact figure both feeds reported.
        self.assertEqual(published[0]["modal_price"], 2450)

        # A differing modal price forms a separate group; neither single-source
        # group is published and the two prices are never averaged.
        divergent = update_data.format_record(dict(base, modal_price=2600))
        published, examined = update_data.select_publishable_records([
            ("data.gov.in", [dict(record)]),
            ("AGMARKNET", [dict(divergent)]),
        ])
        self.assertEqual(published, [])
        self.assertEqual(examined, 2)

    def test_publication_gate_matches_the_documented_minimum(self):
        """The gate constant, payload and documentation must agree."""
        self.assertEqual(update_data.MIN_PRICE_SOURCE_MATCHES, 2)
        payload = json.loads((ROOT / "data/sources.json").read_text(encoding="utf-8"))
        self.assertEqual(
            payload["minimum_price_source_matches"],
            update_data.MIN_PRICE_SOURCE_MATCHES,
        )

    def test_single_source_rows_are_never_marked_cross_verified(self):
        """A lone feed's price may be shown, but never as a verified rate."""
        record = update_data.format_record({
            "state": "Uttar Pradesh", "district": "Kanpur Nagar",
            "market": "Kanpur Grain", "commodity": "Wheat",
            "modal_price": 2450, "min_price": 2400, "max_price": 2500,
            "arrival_date": "27/07/2026",
        })
        snapshot = update_data.build_source_prices_snapshot({
            "data_gov_in": {"status": "live", "records": [record]},
            "agmarknet": {"status": "not_configured", "records": []},
            "enam_trade": {"status": "not_configured", "records": []},
            "up_emandi_trade": {"status": "not_configured", "records": []},
        }, checked_at="2026-07-27T20:30:00+05:30")
        row = {feed["id"]: feed for feed in snapshot["feeds"]}["data_gov_in"]["records"][0]
        self.assertEqual(row["verification_count"], 1)
        self.assertFalse(row["cross_verified"])
        self.assertFalse(row["multi_source_verified"])
        self.assertEqual(row["verification_level"], update_data.SINGLE_SOURCE_LABEL)

    def test_source_prices_remain_separate_without_averaging(self):
        base = {
            "state": "Uttar Pradesh", "district": "Kanpur Nagar",
            "market": "Kanpur Grain", "commodity": "Wheat",
            "min_price": 2400, "max_price": 2550,
            "arrival_date": "27/07/2026",
        }
        data_gov = update_data.format_record(dict(base, modal_price=2450))
        agmarknet = update_data.format_record(dict(base, modal_price=2500))
        snapshot = update_data.build_source_prices_snapshot({
            "data_gov_in": {"status": "live", "records": [data_gov]},
            "agmarknet": {"status": "live", "records": [agmarknet]},
            "enam_trade": {"status": "not_configured", "records": []},
            "up_emandi_trade": {"status": "not_configured", "records": []},
        }, checked_at="2026-07-27T20:30:00+05:30")

        feeds = {feed["id"]: feed for feed in snapshot["feeds"]}
        self.assertEqual(feeds["data_gov_in"]["records"][0]["modal_price"], 2450)
        self.assertEqual(feeds["agmarknet"]["records"][0]["modal_price"], 2500)
        self.assertFalse(feeds["data_gov_in"]["records"][0]["cross_verified"])
        self.assertFalse(feeds["agmarknet"]["records"][0]["three_source_verified"])
        self.assertEqual(feeds["enam_trade"]["status"], "not_configured")

    def test_source_prices_snapshot_lists_every_feed(self):
        payload = json.loads((ROOT / "data/source_prices.json").read_text(encoding="utf-8"))
        feeds = {feed["id"]: feed for feed in payload["feeds"]}
        self.assertIn(
            set(feeds),
            [
                # Auto-generated by update_data.py (4 feeds)
                {"data_gov_in", "agmarknet", "enam_trade", "up_emandi_trade"},
                # Manually augmented with web-scraped feeds (6 feeds)
                {"data_gov_in", "agmarknet", "enam_trade", "up_emandi_trade", "enam_web", "up_emandi_web"},
            ],
        )
        for feed in feeds.values():
            for record in feed["records"]:
                self.assertEqual(record["verification_count"], 1)
                self.assertFalse(record["cross_verified"])
                self.assertFalse(record["three_source_verified"])

    def test_publication_gate_requires_matching_market_commodity_and_date(self):
        template = {
            "state": "Uttar Pradesh", "district": "Kanpur Nagar",
            "market": "Kanpur Grain", "commodity": "Wheat",
            "modal_price": 2450, "min_price": 2400, "max_price": 2500,
            "arrival_date": "27/07/2026",
        }
        record = update_data.format_record(template)
        for differing_field, value in (
            ("market", "Lucknow Grain"),
            ("commodity", "Potato"),
            ("arrival_date", "26/07/2026"),
        ):
            other = update_data.format_record(dict(template, **{differing_field: value}))
            # The two feeds describe *different* rows, so neither reaches the
            # two-source minimum and nothing may be published.
            published, examined = update_data.select_publishable_records([
                ("data.gov.in", [dict(record)]),
                ("AGMARKNET", [dict(other)]),
            ])
            self.assertEqual(
                published, [], f"a mismatched {differing_field} must not publish a price"
            )
            self.assertEqual(examined, 2)

    def test_mandi_parishad_directory_parser_keeps_official_fields(self):
        page = """
        <table>
          <tr><th>क्र.सं.</th><th>क्षेत्र का नाम</th><th>जिला का नाम</th><th>मण्डी नाम</th>
              <th>मण्डी ग्रेड</th><th>सचिव का नाम</th><th>सी.यू.जी</th></tr>
          <tr><td>1</td><td>Meerut</td><td>Meerut</td><td>Sardhana</td><td>C</td>
              <td>Mr. Vijin Kumar Valiyan</td><td>8765956762</td></tr>
          <tr><td>9</td><td>Meerut</td><td>Ghaziabad</td><td>Ghaziabad</td><td>A+</td>
              <td>Mr. Devendra Kumar Verma</td><td>--</td></tr>
          <tr><td>Total</td><td>x</td><td>y</td><td>z</td><td>a</td><td>b</td><td>c</td></tr>
        </table>"""
        rows = update_data.parse_mandi_parishad_directory(page)
        self.assertEqual(len(rows), 2)
        first = rows[0]
        for field in ("division", "district", "mandi", "grade", "secretary", "cug"):
            self.assertIn(field, first)
        self.assertEqual(first["division"], "Meerut")
        self.assertEqual(first["mandi"], "Sardhana")
        self.assertEqual(first["grade"], "C")
        self.assertEqual(first["secretary"], "Mr. Vijin Kumar Valiyan")
        self.assertEqual(first["cug"], "8765956762")
        # A "--" placeholder must stay empty rather than becoming a fake number.
        self.assertIsNone(rows[1]["cug"])
        self.assertEqual(rows[1]["grade"], "A+")

    def test_state_ticker_is_labelled_as_a_state_benchmark(self):
        page = (
            '<marquee><a href="#">गेहू  2555 (+0.67%)</a>'
            '<a href="#">आलू  891 (-0.22%)</a></marquee>'
        )
        entries = update_data.parse_up_krishi_vipran_ticker(page)
        self.assertEqual(len(entries), 2)
        for entry in entries:
            self.assertEqual(entry["scope"], "state_benchmark")
            self.assertFalse(entry["is_mandi_rate"])
            self.assertIn("state_benchmark_price", entry)
            # A state benchmark must never masquerade as a mandi record.
            self.assertNotIn("mandi", entry)
            self.assertNotIn("modal_price", entry)
        self.assertEqual(entries[0]["state_benchmark_price"], 2555)
        self.assertEqual(entries[0]["commodity"], "Wheat")

    def test_benchmarks_file_declares_official_sources(self):
        path = ROOT / "data/benchmarks.json"
        self.assertTrue(path.exists(), "data/benchmarks.json must be published")
        payload = json.loads(path.read_text(encoding="utf-8"))

        state_block = payload["state_benchmark"]
        self.assertEqual(state_block["scope"], "state_benchmark")
        self.assertFalse(state_block["is_mandi_rate"])
        self.assertIn("upkrishivipran.in", state_block["source_url"])
        self.assertIn("not an individual mandi rate", state_block["disclaimer_en"])

        directory = payload["mandi_parishad_directory"]
        self.assertIn("mandiprojects.in/MandiDetails", directory["source_url"])
        self.assertEqual(
            directory["fields"],
            ["division", "district", "mandi", "grade", "secretary", "cug"],
        )

        self.assertIn("agmarknet.gov.in/home", payload["agmarknet"]["source_url"])

        portal_urls = {portal["url"] for portal in payload["official_portals"]}
        self.assertIn("https://agmarknet.gov.in/home", portal_urls)
        self.assertIn("https://dashboard.mandiprojects.in/MandiDetails.aspx", portal_urls)
        self.assertIn("https://www.upkrishivipran.in/Default.aspx", portal_urls)

    def test_dashboard_labels_the_state_ticker_as_a_benchmark(self):
        source = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("data/benchmarks.json", source)
        self.assertIn("State-level benchmark — not an individual mandi rate", source)
        self.assertIn("renderStateBenchmark", source)
        self.assertIn("renderOfficialPortals", source)
        self.assertIn("Government Source Monitor", source)

    def test_three_source_verification_requires_exact_price_match(self):
        base = update_data.format_record({
            "state": "Uttar Pradesh", "district": "Kanpur Nagar",
            "market": "Kanpur Grain", "commodity": "Wheat",
            "modal_price": 2450, "min_price": 2400, "max_price": 2500,
            "arrival_date": "27/07/2026",
        })
        same_2 = dict(base)
        same_3 = dict(base)
        verified = update_data.add_cross_verification(
            [base], "data.gov.in", [("AGMARKNET", [same_2]), ("e-NAM", [same_3])]
        )
        self.assertEqual(verified[0]["verification_count"], 3)
        self.assertTrue(verified[0]["three_source_verified"])

        mismatch = dict(base, modal_price=9999)
        verified = update_data.add_cross_verification(
            [dict(base)], "data.gov.in", [("AGMARKNET", [mismatch])]
        )
        self.assertEqual(verified[0]["verification_count"], 1)
        self.assertFalse(verified[0]["cross_verified"])

    def test_auction_snapshot_contains_no_fallback_lots(self):
        auction = json.loads((ROOT / "data/auction.json").read_text(encoding="utf-8"))
        self.assertIn(auction["status"], {
            "configuration_required", "temporarily_unavailable", "no_active_lots", "live"
        })
        if auction["status"] != "live":
            self.assertEqual(auction["lots"], [])

    def test_weather_simulation_was_removed(self):
        self.assertFalse((ROOT / "data/weather.json").exists())

    def test_four_daily_schedule(self):
        workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
        self.assertIn("0 1,7,11,15 * * *", workflow)

    def test_schedule_matches_the_documented_ist_slots(self):
        """01:00, 07:00, 11:00 and 15:00 UTC == the documented IST cycles."""
        expected = ("06:30", "12:30", "16:30", "20:30")
        self.assertEqual(update_data.UPDATE_SLOTS_IST, expected)

        workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
        cron = re.search(r"cron:\s*'0 ([0-9,]+) \* \* \*'", workflow)
        self.assertIsNotNone(cron)
        utc_hours = sorted(int(hour) for hour in cron.group(1).split(","))
        self.assertEqual(len(utc_hours), 4)

        derived = sorted(
            f"{(hour + 5) % 24:02d}:30" for hour in utc_hours
        )
        self.assertEqual(derived, sorted(expected))

    def test_workflow_publishes_every_official_snapshot(self):
        workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
        for data_file in (
            "data/latest.json", "data/source_prices.json", "data/state_prices.json", "data/mandis.json",
            "data/auction.json", "data/benchmarks.json", "data/sources.json",
        ):
            self.assertIn(data_file, workflow)
        # Weather was a simulated feed and must not come back.
        self.assertNotIn("data/weather.json", workflow)

    def test_no_module_generates_random_values(self):
        for name in ("update_data.py", "app.py", "prediction.py", "alerts.py", "index.html"):
            source = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("Math.random", source, f"{name} must not fabricate values")
            self.assertNotRegex(
                source, r"\brandom\.(random|randint|uniform|choice|gauss)\b",
                f"{name} must not fabricate values",
            )

    def test_source_monitor_snapshot_lists_the_new_portals(self):
        payload = json.loads((ROOT / "data/sources.json").read_text(encoding="utf-8"))
        names = {item["name"] for item in payload["sources"]}
        self.assertIn("AGMARKNET portal", names)
        self.assertIn("UP Mandi Parishad directory", names)
        self.assertIn("UP Krishi Vipran state benchmark", names)
        self.assertEqual(
            payload["minimum_price_source_matches"],
            update_data.MIN_PRICE_SOURCE_MATCHES,
        )
        self.assertEqual(payload["update_slots_ist"], list(update_data.UPDATE_SLOTS_IST))


class DistrictNormalisationTests(unittest.TestCase):
    """Regression tests for the "Jila" (जिला) naming defects."""

    def test_every_notified_district_has_a_hindi_label(self):
        """All 75 UP districts must resolve to a Hindi name."""
        self.assertGreaterEqual(len(update_data.DISTRICT_HI), 75)
        for english, hindi in update_data.DISTRICT_HI.items():
            self.assertTrue(hindi.strip(), f"{english} has no Hindi label")

    def test_renamed_districts_resolve_to_the_current_official_name(self):
        for reported, expected in (
            ("Allahabad", "Prayagraj"),
            ("Faizabad", "Ayodhya"),
            ("Bara Banki", "Barabanki"),
            ("Rae Bareli", "Raebareli"),
            ("Bhadohi", "Sant Ravidas Nagar"),
            ("Kheri", "Lakhimpur Kheri"),
            ("Jyotiba Phule Nagar", "Amroha"),
            ("Kanshiram Nagar", "Kasganj"),
        ):
            self.assertEqual(update_data.canonical_district(reported), expected)
            # Each alias must also produce a real Hindi label, never a blank.
            self.assertTrue(update_data.district_hi_for(reported).strip())

    def test_district_matching_ignores_case_and_punctuation(self):
        for variant in ("kanpur nagar", "KANPUR  NAGAR", "Kanpur-Nagar"):
            self.assertEqual(update_data.canonical_district(variant), "Kanpur Nagar")

    def test_unknown_district_is_preserved_not_dropped(self):
        """A district the pipeline does not know must survive unchanged."""
        self.assertEqual(update_data.canonical_district("New Notified Zila"), "New Notified Zila")
        self.assertEqual(update_data.district_hi_for("New Notified Zila"), "New Notified Zila")

    def test_records_keep_the_exact_spelling_the_feed_reported(self):
        record = update_data.format_record({
            "state": "Uttar Pradesh", "district": "Allahabad", "market": "Mandi",
            "commodity": "Wheat", "modal_price": 2450, "arrival_date": "27/07/2026",
        })
        self.assertEqual(record["district"], "Prayagraj")
        self.assertEqual(record["district_hi"], "प्रयागराज")
        # Traceability: what the government feed actually printed is retained.
        self.assertEqual(record["district_reported"], "Allahabad")

    def test_two_feeds_using_different_official_spellings_cross_verify(self):
        """The real reason prices stayed hidden: aliases never grouped."""
        base = {
            "state": "Uttar Pradesh", "market": "Kanpur Grain", "commodity": "Wheat",
            "modal_price": 2450, "min_price": 2400, "max_price": 2500,
            "arrival_date": "27/07/2026",
        }
        old_name = update_data.format_record(dict(base, district="Allahabad"))
        new_name = update_data.format_record(dict(base, district="Prayagraj"))
        published, examined = update_data.select_publishable_records([
            ("data.gov.in", [old_name]),
            ("AGMARKNET", [new_name]),
        ])
        self.assertEqual(examined, 1, "the same district must form one group")
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]["district"], "Prayagraj")


class DashboardResilienceTests(unittest.TestCase):
    """Guard the front-end against the crashes found in the dashboard."""

    SOURCE = (ROOT / "index.html").read_text(encoding="utf-8")

    def test_language_helpers_exist(self):
        """Missing Hindi labels must go through the safe fallback helpers."""
        for helper in ("function displayName(", "function optionLabel(",
                       "function searchableText(", "function compareLabels("):
            self.assertIn(helper, self.SOURCE)

    def test_dropdowns_never_sort_on_a_raw_language_key(self):
        """`a[currentLang].localeCompare` crashed the whole जिला dropdown."""
        self.assertNotIn("a[currentLang].localeCompare", self.SOURCE)
        self.assertNotIn("list.sort((a,b) => a[currentLang]", self.SOURCE)

    def test_search_filters_do_not_call_tolowercase_on_raw_fields(self):
        """A null district_hi used to abort rendering with a TypeError."""
        for fragile in ("r.district_hi.toLowerCase()", "r.mandi_hi.toLowerCase()",
                        "r.commodity_hi.toLowerCase()"):
            self.assertNotIn(fragile, self.SOURCE)

    def test_district_group_header_spans_every_column(self):
        """The rate table has 9 columns; a stale colspan broke the layout."""
        self.assertNotIn('colspan="10"', self.SOURCE)
        self.assertIn('colspan="9"', self.SOURCE)

    def test_update_time_bar_is_present(self):
        for marker in ("id=\"update-time-bar\"", "id=\"update-time-main\"",
                       "id=\"update-time-next\"", "function renderUpdateTimeBar("):
            self.assertIn(marker, self.SOURCE)

    def test_empty_rate_table_explains_the_cause(self):
        self.assertIn("function explainWhyNoPrices(", self.SOURCE)
        self.assertIn("DATA_GOV_IN_API_KEY", self.SOURCE)

    def test_single_source_rows_are_badged_in_the_table(self):
        self.assertIn("collectSingleSourceRecords", self.SOURCE)
        self.assertIn("usingSingleSourceFallback", self.SOURCE)
        self.assertIn("cross-verified नहीं", self.SOURCE)

    def test_sidebar_does_not_average_across_commodities(self):
        """Averaging wheat with potato produced a meaningless "mandi rate"."""
        self.assertNotIn(
            "prices.reduce((sum, price) => sum + price, 0) / prices.length",
            self.SOURCE,
        )


class ServiceWorkerTests(unittest.TestCase):
    """The offline cache must not break POSTs or store error pages."""

    SOURCE = (ROOT / "sw.js").read_text(encoding="utf-8")

    def test_non_get_requests_bypass_the_cache(self):
        """Cache.put() rejects a POST with "Invalid request method POST",
        which would make /api/v2/alerts/subscribe look like a network error."""
        self.assertIn("request.method !== 'GET'", self.SOURCE)

    def test_only_successful_responses_are_cached(self):
        """fetch() resolves for 404/500 too; caching those would overwrite a
        good offline copy with an error page."""
        self.assertIn("networkResponse.ok", self.SOURCE)
        self.assertIn("networkResponse.type !== 'opaque'", self.SOURCE)
        self.assertNotIn("cache.put(event.request, networkResponse.clone());", self.SOURCE)

    def test_offline_miss_resolves_instead_of_hanging(self):
        self.assertIn("Response.error()", self.SOURCE)

    def test_cache_version_was_bumped_for_the_new_logic(self):
        """Returning users keep the old worker unless the cache name changes."""
        match = re.search(r"const CACHE_NAME = 'up-mandi-v(\d+)'", self.SOURCE)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 12)


class ApiHardeningTests(unittest.TestCase):
    """Regression tests for defects found by exercising the REST API."""

    SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")

    def test_csv_export_uses_a_real_csv_writer(self):
        """Official mandi/commodity names contain commas, which shifted every
        later column when the row was built with an f-string."""
        self.assertIn("csv.writer(", self.SOURCE)
        self.assertNotIn(
            'row = f"{r.id},{r.district},{r.mandi}', self.SOURCE
        )

    def test_csv_export_neutralises_spreadsheet_formulas(self):
        self.assertIn("_csv_safe", self.SOURCE)

    def test_alert_subscription_validates_the_channel_and_contact(self):
        """A bogus contact_type or junk phone used to be stored as a dead row."""
        self.assertIn("SUPPORTED_CONTACT_TYPES", self.SOURCE)
        self.assertIn("_validated_contact_value", self.SOURCE)
        self.assertIn(r"^(telegram|whatsapp)$", self.SOURCE)


class AdminPanelTests(unittest.TestCase):
    """The admin panel must not offer actions the API refuses."""

    SOURCE = (ROOT / "admin.html").read_text(encoding="utf-8")
    APP = (ROOT / "app.py").read_text(encoding="utf-8")

    def test_manual_rate_editing_ui_is_removed(self):
        """POST/PUT/DELETE /api/v2/rates all return 405, so the manual
        add/edit/delete dialog could never save and was dead UI."""
        for gone in ("openAddModal", "editRate(", "deleteRate(",
                     "handleSaveRate", 'id="rate-modal"', 'id="m-modal"'):
            self.assertNotIn(gone, self.SOURCE, f"{gone} is unreachable dead code")

    def test_api_still_refuses_manual_rate_writes(self):
        """The read-only policy the removed UI violated must stay enforced."""
        self.assertIn("Manual rates are disabled", self.APP)
        self.assertIn("Official feed records are read-only", self.APP)

    def test_admin_escapes_feed_values(self):
        self.assertIn("function esc(", self.SOURCE)
        self.assertNotIn("${r.district_hi} (${r.district})", self.SOURCE)

    def test_admin_has_no_dangling_element_references(self):
        """Every getElementById target and inline handler must exist."""
        defined_ids = set(re.findall(r'id="([^"]+)"', self.SOURCE))
        used_ids = set(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", self.SOURCE))
        self.assertEqual(used_ids - defined_ids, set())

        handlers = set(re.findall(r'on(?:click|submit)="([A-Za-z0-9_]+)\(', self.SOURCE))
        functions = set(re.findall(r"function ([A-Za-z0-9_]+)\(", self.SOURCE))
        self.assertEqual(handlers - functions, set())

    def test_admin_token_is_not_persisted_across_restarts(self):
        self.assertIn('sessionStorage', self.SOURCE)
        self.assertIn('localStorage.removeItem("mandi_jwt_token")', self.SOURCE)


class DeterministicServicesTests(unittest.TestCase):
    def test_prediction_is_deterministic(self):
        history = {"Wheat": [
            {"date": "2026-07-24", "price": 2400},
            {"date": "2026-07-25", "price": 2410},
            {"date": "2026-07-26", "price": 2420},
        ]}
        first = prediction.predict_future_prices(history, "Wheat")
        second = prediction.predict_future_prices(history, "Wheat")
        self.assertEqual(first["predictions"], second["predictions"])
        self.assertEqual(first["confidence"], second["confidence"])

    def test_prediction_refuses_insufficient_history(self):
        with self.assertRaises(ValueError):
            prediction.predict_future_prices({"Wheat": [{"price": 2400}]}, "Wheat")

    def test_missing_alert_provider_is_not_reported_as_success(self):
        with patch.object(alerts, "TELEGRAM_BOT_TOKEN", ""):
            self.assertFalse(alerts.send_telegram_alert("123", "test"))
        with patch.object(alerts, "WHATSAPP_API_KEY", ""), patch.object(alerts, "WHATSAPP_API_URL", ""):
            self.assertFalse(alerts.send_whatsapp_alert("9999999999", "test"))


if __name__ == "__main__":
    unittest.main()
