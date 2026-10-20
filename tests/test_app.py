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

    def test_mandi_ai_requires_server_side_provider_key(self):
        provider_vars = ("AI_API_BASE_URL", "AI_API_KEY", "OPENROUTER_API_KEY")
        previous = {name: os.environ.pop(name, None) for name in provider_vars}
        try:
            response = self.client.post("/api/v2/mandi-ai", json={
                "userQuestion": "Aligarh me Masur Dal ka bhav kya hai?",
            })
        finally:
            for name, value in previous.items():
                if value is not None:
                    os.environ[name] = value
        self.assertEqual(response.status_code, 503)
        self.assertIn("OPENROUTER_API_KEY", response.text)
        self.assertIn("AI_API_KEY", response.text)

    def test_freellmapi_openai_compatible_endpoint_uses_its_own_key(self):
        import io
        import json
        from unittest.mock import patch

        config = {
            "AI_API_BASE_URL": "http://freellmapi:3001/v1",
            "AI_API_KEY": "freellmapi-unified-test-key",
            "AI_MODEL": "",
            "AI_VISION_MODEL": "",
            "OPENROUTER_API_KEY": "must-not-be-forwarded",
            "OPENROUTER_MODEL": "openrouter-model-should-not-be-used",
            "OPENROUTER_SITE_URL": "https://example.invalid/",
        }
        fake_response = io.BytesIO(
            b'{"choices":[{"message":{"content":"Namaste"}}],"model":"gemini-2.5-flash"}'
        )
        with patch.dict(os.environ, config), patch(
            "app.urllib.request.urlopen", return_value=fake_response
        ) as mocked_urlopen:
            answer, model = mandi_app._call_ai_chat([
                {"role": "user", "content": "Namaste"},
            ])

        request = mocked_urlopen.call_args.args[0]
        request_headers = {key.lower(): value for key, value in request.header_items()}
        request_body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "http://freellmapi:3001/v1/chat/completions")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request_headers["authorization"], "Bearer freellmapi-unified-test-key")
        self.assertNotIn("http-referer", request_headers)
        self.assertNotIn("x-title", request_headers)
        self.assertEqual(request_body["model"], "auto")
        self.assertEqual(answer, "Namaste")
        self.assertEqual(model, "gemini-2.5-flash")

    def test_custom_ai_endpoint_never_falls_back_to_openrouter_key(self):
        from fastapi import HTTPException
        from unittest.mock import patch

        with patch.dict(os.environ, {
            "AI_API_BASE_URL": "http://freellmapi:3001/v1",
            "AI_API_KEY": "",
            "OPENROUTER_API_KEY": "do-not-send-to-custom-provider",
        }):
            with self.assertRaises(HTTPException) as raised:
                mandi_app._call_ai_chat([{"role": "user", "content": "hello"}])
        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("AI_API_KEY", raised.exception.detail)

    def test_existing_openrouter_environment_settings_still_work(self):
        import io
        import json
        from unittest.mock import patch

        config = {
            "AI_API_BASE_URL": "",
            "AI_API_KEY": "",
            "AI_MODEL": "",
            "AI_VISION_MODEL": "",
            "OPENROUTER_API_KEY": "openrouter-test-key",
            "OPENROUTER_MODEL": "deepseek/test:free",
            "OPENROUTER_SITE_URL": "https://mandi.example/",
            "OPENROUTER_APP_NAME": "Mandi test",
        }
        fake_response = io.BytesIO(
            b'{"choices":[{"message":{"content":"Namaste"}}]}'
        )
        with patch.dict(os.environ, config), patch(
            "app.urllib.request.urlopen", return_value=fake_response
        ) as mocked_urlopen:
            answer, model = mandi_app._call_ai_chat([
                {"role": "user", "content": "Namaste"},
            ])

        request = mocked_urlopen.call_args.args[0]
        request_headers = {key.lower(): value for key, value in request.header_items()}
        request_body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(request_headers["authorization"], "Bearer openrouter-test-key")
        self.assertEqual(request_headers["http-referer"], "https://mandi.example/")
        self.assertEqual(request_headers["x-title"], "Mandi test")
        self.assertEqual(request_body["model"], "deepseek/test:free")
        self.assertEqual(answer, "Namaste")
        self.assertEqual(model, "deepseek/test:free")

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
