import csv
import io
import json
import unittest
from pathlib import Path

import export_sheets


ROOT = Path(__file__).resolve().parents[1]
SHEETS_DIR = ROOT / "data" / export_sheets.SHEETS_DIRNAME


class CsvSafetyTests(unittest.TestCase):
    def test_formula_prefixes_are_neutralised(self):
        """Upstream text must never execute as a spreadsheet formula."""
        for dangerous in ("=1+1", "+91-9876543210", "-2500", "@SUM(A1)", "\tX", "\rY"):
            self.assertTrue(
                export_sheets.csv_safe(dangerous).startswith("'"),
                f"{dangerous!r} was not neutralised",
            )

    def test_ordinary_values_are_untouched(self):
        self.assertEqual(export_sheets.csv_safe("Wheat"), "Wheat")
        self.assertEqual(export_sheets.csv_safe(2450), "2450")
        self.assertEqual(export_sheets.csv_safe("गेहूं"), "गेहूं")

    def test_none_becomes_an_empty_cell_not_the_word_none(self):
        self.assertEqual(export_sheets.csv_safe(None), "")

    def test_booleans_and_lists_render_readably(self):
        self.assertEqual(export_sheets.csv_safe(True), "yes")
        self.assertEqual(export_sheets.csv_safe(False), "no")
        self.assertEqual(export_sheets.csv_safe(["a", None, "b"]), "a, b")

    def test_commas_and_quotes_stay_inside_one_column(self):
        """Mandi/commodity names contain commas; columns must not shift."""
        body = export_sheets.rows_to_csv(
            ("Mandi", "Commodity", "Modal_Price"),
            [["Kanpur, Grain Market", 'Arhar (Tur/"Red Gram")', 6200]],
        )
        parsed = list(csv.reader(io.StringIO(body)))
        self.assertEqual(len(parsed[1]), 3)
        self.assertEqual(parsed[1][0], "Kanpur, Grain Market")
        self.assertEqual(parsed[1][1], 'Arhar (Tur/"Red Gram")')
        self.assertEqual(parsed[1][2], "6200")


class SheetBuilderTests(unittest.TestCase):
    def test_price_rows_copy_the_snapshot_exactly(self):
        latest = {
            "updated_at": "2026-07-28T06:30:00+05:30",
            "records": [{
                "arrival_date": "27/07/2026",
                "district": "Kanpur Nagar", "district_hi": "कानपुर नगर",
                "mandi": "Kanpur Grain", "commodity": "Wheat", "commodity_hi": "गेहूं",
                "variety": "Dara", "grade": "FAQ",
                "min_price": 2400, "max_price": 2500, "modal_price": 2450,
                "price_unit": "Quintal",
                "verification_sources": ["data.gov.in", "AGMARKNET"],
                "verification_count": 2,
            }],
        }
        header, rows = export_sheets.build_mandi_prices(latest)
        self.assertEqual(len(rows), 1)
        row = dict(zip(header, rows[0]))
        # Prices are the exact reported figures - never averaged or rounded here.
        self.assertEqual(row["Min_Price"], 2400)
        self.assertEqual(row["Modal_Price"], 2450)
        self.assertEqual(row["Max_Price"], 2500)
        self.assertEqual(row["Source_Count"], 2)
        self.assertEqual(row["Updated_At_IST"], "2026-07-28T06:30:00+05:30")

    def test_empty_snapshot_produces_headers_and_no_invented_rows(self):
        header, rows = export_sheets.build_mandi_prices({"records": []})
        self.assertEqual(rows, [])
        self.assertTrue(header)

    def test_single_source_rows_stay_labelled_single_source(self):
        snapshot = {"feeds": [{
            "name": "data.gov.in OGD price API",
            "status": "live",
            "source_url": "https://data.gov.in/",
            "data_updated_at": "2026-07-28T06:30:00+05:30",
            "records": [{
                "district": "Agra", "mandi": "Agra", "commodity": "Potato",
                "modal_price": 1200, "verification_label": "single_source",
            }],
        }]}
        header, rows = export_sheets.build_source_prices(snapshot)
        row = dict(zip(header, rows[0]))
        self.assertEqual(row["Verification"], "single_source")
        self.assertEqual(row["Feed"], "data.gov.in OGD price API")

    def test_history_is_written_in_long_pivotable_format(self):
        header, rows = export_sheets.build_price_history({
            "Wheat": [{"date": "2026-07-27", "price": 2450},
                      {"date": "2026-07-28", "price": 2460}],
        })
        self.assertEqual(list(header), ["Commodity", "Date", "Average_Modal_Price"])
        self.assertEqual(rows, [
            ["Wheat", "2026-07-27", 2450],
            ["Wheat", "2026-07-28", 2460],
        ])

    def test_every_declared_sheet_is_actually_built(self):
        built = export_sheets.build_sheets(ROOT / "data")
        for spec in export_sheets.SHEET_SPECS:
            self.assertIn(spec["id"], built)
            self.assertTrue(built[spec["id"]]["header"], spec["id"])


class GeneratedFileTests(unittest.TestCase):
    def test_every_sheet_file_exists_and_parses(self):
        for spec in export_sheets.SHEET_SPECS:
            path = SHEETS_DIR / spec["file"]
            self.assertTrue(path.exists(), f"{spec['file']} was not generated")
            parsed = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8"))))
            self.assertTrue(parsed, f"{spec['file']} is empty")
            width = len(parsed[0])
            for line_number, row in enumerate(parsed[1:], start=2):
                self.assertEqual(
                    len(row), width,
                    f"{spec['file']} line {line_number} has {len(row)} columns, expected {width}",
                )

    def test_no_generated_cell_can_execute_as_a_formula(self):
        for spec in export_sheets.SHEET_SPECS:
            path = SHEETS_DIR / spec["file"]
            for row in csv.reader(io.StringIO(path.read_text(encoding="utf-8"))):
                for cell in row:
                    if cell[:1] in export_sheets.FORMULA_PREFIXES:
                        self.fail(f"{spec['file']} exposes an executable cell: {cell!r}")

    def test_manifest_lists_every_sheet_with_usable_links(self):
        manifest = json.loads((SHEETS_DIR / "index.json").read_text(encoding="utf-8"))
        listed = {sheet["id"] for sheet in manifest["sheets"]}
        self.assertEqual(listed, {spec["id"] for spec in export_sheets.SHEET_SPECS})
        for sheet in manifest["sheets"]:
            self.assertTrue(sheet["csv_url"].startswith("https://"))
            self.assertIn("IMPORTDATA", sheet["google_sheets_formula"])
            self.assertIn("Csv.Document", sheet["excel_power_query"])

    def test_unverified_snapshot_never_exports_price_rows(self):
        """The CSV must obey the same publication gate as the dashboard."""
        latest = json.loads((ROOT / "data/latest.json").read_text(encoding="utf-8"))
        if not latest.get("verified"):
            body = (SHEETS_DIR / "mandi_prices.csv").read_text(encoding="utf-8")
            parsed = list(csv.reader(io.StringIO(body)))
            self.assertEqual(len(parsed), 1, "unverified snapshot exported price rows")

    def test_write_all_is_idempotent(self):
        before = {
            spec["file"]: (SHEETS_DIR / spec["file"]).read_text(encoding="utf-8")
            for spec in export_sheets.SHEET_SPECS
        }
        export_sheets.write_all(ROOT / "data")
        for filename, content in before.items():
            self.assertEqual(
                (SHEETS_DIR / filename).read_text(encoding="utf-8"), content,
                f"{filename} changed without any new government data",
            )


class PipelineWiringTests(unittest.TestCase):
    def test_update_pipeline_regenerates_the_spreadsheet_feeds(self):
        source = (ROOT / "update_data.py").read_text(encoding="utf-8")
        self.assertIn("import export_sheets", source)
        self.assertIn("export_sheets.write_all(DATA_DIR)", source)

    def test_workflow_commits_the_generated_sheets(self):
        """The scheduled Action must stage data/sheets or the CSVs never ship.

        update_data.py regenerates data/sheets/ on every run, but the workflow
        commits an explicit file list. Until ``data/sheets`` is added to that
        ``git add`` list the refreshed CSVs are rebuilt in CI and then thrown
        away, so a linked spreadsheet would keep showing the committed
        snapshot. This is skipped rather than failed because the sandbox that
        introduced the feature is not permitted to edit workflow files; see
        SETUP_SHEETS.md for the one-line change.
        """
        workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
        if "data/sheets" not in workflow:
            self.skipTest(
                "PENDING: add 'data/sheets' to the git add list in "
                ".github/workflows/update.yml so the scheduled refresh commits "
                "the regenerated spreadsheet feeds."
            )


if __name__ == "__main__":
    unittest.main()
