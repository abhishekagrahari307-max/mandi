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
            self.assertEqual(latest.get("records"), [])

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

    def test_prices_publish_only_with_three_matching_government_feeds(self):
        base = {
            "state": "Uttar Pradesh", "district": "Kanpur Nagar",
            "market": "Kanpur Grain", "commodity": "Wheat",
            "modal_price": 2450, "min_price": 2400, "max_price": 2500,
            "arrival_date": "27/07/2026",
        }
        record = update_data.format_record(base)

        # Two agreeing feeds are not enough for publication.
        published, examined = update_data.select_publishable_records([
            ("data.gov.in", [dict(record)]),
            ("AGMARKNET", [dict(record)]),
        ])
        self.assertEqual(published, [])
        self.assertEqual(examined, 1)

        # Three agreeing feeds publish exactly one record.
        published, examined = update_data.select_publishable_records([
            ("data.gov.in", [dict(record)]),
            ("AGMARKNET", [dict(record)]),
            ("e-NAM trade feed", [dict(record)]),
        ])
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]["verification_count"], 3)
        self.assertTrue(published[0]["three_source_verified"])

        # A differing modal price forms a separate group and is not published.
        divergent = update_data.format_record(dict(base, modal_price=2600))
        published, examined = update_data.select_publishable_records([
            ("data.gov.in", [dict(record)]),
            ("AGMARKNET", [dict(record)]),
            ("e-NAM trade feed", [dict(divergent)]),
        ])
        self.assertEqual(published, [])
        self.assertEqual(examined, 2)

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
            published, _ = update_data.select_publishable_records([
                ("data.gov.in", [dict(record)]),
                ("AGMARKNET", [dict(record)]),
                ("e-NAM trade feed", [dict(other)]),
            ])
            self.assertEqual(
                published, [], f"a mismatched {differing_field} must not publish a price"
            )

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

    def test_six_daily_schedule(self):
        workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
        self.assertIn("0 3,7,11,15,19,23 * * *", workflow)

    def test_schedule_matches_the_documented_ist_slots(self):
        """00:30, 04:30, 08:30, 12:30, 16:30 and 20:30 IST == UTC+5:30."""
        expected = ("00:30", "04:30", "08:30", "12:30", "16:30", "20:30")
        self.assertEqual(update_data.UPDATE_SLOTS_IST, expected)

        workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
        cron = re.search(r"cron:\s*'0 ([0-9,]+) \* \* \*'", workflow)
        self.assertIsNotNone(cron)
        utc_hours = sorted(int(hour) for hour in cron.group(1).split(","))
        self.assertEqual(len(utc_hours), 6)

        derived = sorted(
            f"{(hour + 5) % 24:02d}:30" for hour in utc_hours
        )
        self.assertEqual(derived, sorted(expected))

    def test_workflow_publishes_every_official_snapshot(self):
        workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
        for data_file in (
            "data/latest.json", "data/state_prices.json", "data/mandis.json",
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
        self.assertEqual(payload["minimum_price_source_matches"], 3)
        self.assertEqual(payload["update_slots_ist"], list(update_data.UPDATE_SLOTS_IST))


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
