import os
import tempfile
import unittest
from pathlib import Path


TEST_DB = tempfile.NamedTemporaryFile(prefix="mandi-test-", suffix=".db", delete=False)
TEST_DB.close()

# Configure the application before importing it. Production mode ensures the
# tests exercise the same fail-closed authentication path used by Docker.
os.environ["ENVIRONMENT"] = "production"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.name}"
os.environ["JWT_SECRET"] = "test-jwt-secret-that-is-at-least-32-bytes"
os.environ["ADMIN_USERNAME"] = "testadmin"
os.environ["ADMIN_PASSWORD"] = "correct-horse-battery-staple"
os.environ["ADMIN_EMAIL"] = "testadmin@example.com"
os.environ["CORS_ORIGINS"] = "http://testserver"

from fastapi.testclient import TestClient  # noqa: E402
import app as mandi_app  # noqa: E402


class AppSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_context = TestClient(mandi_app.app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        Path(TEST_DB.name).unlink(missing_ok=True)

    def test_health_and_dashboard(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "healthy")
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_configured_admin_can_log_in(self):
        response = self.client.post(
            "/api/v2/auth/login",
            data={
                "username": "testadmin",
                "password": "correct-horse-battery-staple",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["access_token"])

    def test_old_default_credentials_are_rejected(self):
        response = self.client.post(
            "/api/v2/auth/login",
            data={"username": "admin", "password": "admin123"},
        )
        self.assertEqual(response.status_code, 401)

    def test_rates_limit_is_honored(self):
        response = self.client.get("/api/v2/rates?limit=2")
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.json()["records"]), 2)

    def test_auction_does_not_create_local_bids(self):
        snapshot = self.client.get("/api/v2/auction/lots")
        self.assertEqual(snapshot.status_code, 200)
        self.assertIn("lots", snapshot.json())

        bid = self.client.post("/api/v2/auction/bid", json={
            "lot_number": "FAKE-LOT",
            "bid_amount": 2500,
            "trader_name": "Test Trader",
        })
        self.assertEqual(bid.status_code, 503)
        self.assertIn("official e-NAM", bid.text)

    def test_prediction_refuses_unverified_history(self):
        response = self.client.get("/api/v2/prediction/Wheat")
        self.assertEqual(response.status_code, 503)

    def test_csv_export_keeps_columns_aligned_and_inert(self):
        """Official names contain commas and quotes, and a leading '=' is
        executed as a formula by Excel. Both must be handled."""
        import csv
        import io

        session = mandi_app.db.SessionLocal()
        try:
            session.add(mandi_app.db.MandiRecord(
                district="Kanpur Nagar", district_hi="कानपुर नगर",
                mandi="Kanpur, Grain Market", mandi_hi="कानपुर गल्ला",
                commodity="Arhar (Tur/Red Gram)(Whole)", commodity_hi="अरहर",
                variety='Dara "FAQ"', grade="FAQ", arrivals=None,
                min_price=2400, max_price=2500, modal_price=2450,
                arrival_date="27/07/2026",
            ))
            session.add(mandi_app.db.MandiRecord(
                district="=cmd|'/C calc'!A0", district_hi="x",
                mandi="X", mandi_hi="X", commodity="Y", commodity_hi="Y",
                variety="V", grade="G", arrivals=1,
                min_price=1, max_price=2, modal_price=1,
                arrival_date="27/07/2026",
            ))
            session.commit()
        finally:
            session.close()

        body = self.client.get("/api/v2/excel/sync").text
        rows = list(csv.reader(io.StringIO(body)))
        self.assertGreaterEqual(len(rows), 3)
        width = len(rows[0])
        for row in rows[1:]:
            self.assertEqual(len(row), width, f"misaligned CSV row: {row}")

        # The comma inside the mandi name must stay in a single cell.
        commas = [r for r in rows if "Kanpur, Grain Market" in r]
        self.assertEqual(len(commas), 1)
        # No cell may start with a spreadsheet formula trigger.
        for row in rows:
            for cell in row:
                self.assertNotIn(cell[:1], ("=", "+", "@"))

    def test_alert_subscription_rejects_undeliverable_contacts(self):
        for payload in (
            {"contact_type": "carrier-pigeon", "contact_value": "9876543210"},
            {"contact_type": "whatsapp", "contact_value": "not-a-phone!!"},
            {"contact_type": "whatsapp", "contact_value": "<script>x</script>"},
            {"contact_type": "telegram", "contact_value": "abcdefgh"},
        ):
            response = self.client.post("/api/v2/alerts/subscribe", json=payload)
            self.assertEqual(
                response.status_code, 422,
                f"{payload} should not create a dead subscription",
            )

    def test_alert_subscription_accepts_a_valid_contact(self):
        response = self.client.post("/api/v2/alerts/subscribe", json={
            "contact_type": "whatsapp", "contact_value": "+91 98765-43210",
        })
        self.assertEqual(response.status_code, 200)
        # The stored value is normalised, and a missing provider is never
        # reported as a successful delivery.
        self.assertFalse(response.json()["welcome_delivered"])


if __name__ == "__main__":
    unittest.main()
