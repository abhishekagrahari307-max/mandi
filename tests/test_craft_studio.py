import json
import re
import unittest
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parent.parent / "craft-studio"


class CraftStudioTests(unittest.TestCase):
    def test_hub_index_and_manifest_exist(self):
        self.assertTrue((STUDIO_ROOT / "index.html").is_file())
        self.assertTrue((STUDIO_ROOT / ".nojekyll").is_file())
        manifest = json.loads((STUDIO_ROOT / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertIn("Craft Studio", manifest["name"])

    def test_all_14_apps_aliases_icons_and_screenshots_exist(self):
        catalog = (STUDIO_ROOT / "assets/catalog.js").read_text(encoding="utf-8")
        app_ids = [
            a for a in re.findall(r'id:\s*"([^"]+)"', catalog)
            if a not in ("all", "excel", "photo", "pdf", "design", "media", "cad")
        ]
        self.assertEqual(len(app_ids), 14)
        for app_id in app_ids:
            app_entry = STUDIO_ROOT / "apps" / app_id / "index.html"
            self.assertTrue(app_entry.is_file(), f"Missing studio app entry: {app_entry}")

        for alias in re.findall(r'alias:\s*"([^"]+)"', catalog):
            self.assertTrue((STUDIO_ROOT / alias / "index.html").is_file(), f"Missing alias: {alias}")

        for rel in re.findall(r'(?:icon|src):\s*"\.\/([^"]+)"', catalog):
            self.assertTrue((STUDIO_ROOT / rel).is_file(), f"Missing asset: {rel}")

    def test_releases_metadata_and_vendor_bundles_exist(self):
        releases = json.loads((STUDIO_ROOT / "assets/releases.json").read_text(encoding="utf-8"))
        self.assertEqual(len(releases), 14)
        for bundle in (
            "xlsx.bundle.js",
            "psd.bundle.js",
            "pdf.bundle.js",
            "pdf.worker.min.mjs",
            "office.bundle.js",
        ):
            path = STUDIO_ROOT / "vendor" / bundle
            self.assertTrue(path.is_file() and path.stat().st_size > 10_000, f"Invalid bundle: {path}")


if __name__ == "__main__":
    unittest.main()
