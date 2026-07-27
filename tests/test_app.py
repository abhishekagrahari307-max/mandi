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


if __name__ == "__main__":
    unittest.main()
