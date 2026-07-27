import json
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
