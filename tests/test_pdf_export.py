import re
import unittest
from pathlib import Path


INDEX_HTML = Path(__file__).resolve().parents[1] / "index.html"
SOURCE = INDEX_HTML.read_text(encoding="utf-8")


class PdfExportRegressionTests(unittest.TestCase):
    def test_export_element_is_attached_until_capture_finishes(self):
        helper = re.search(
            r"async function savePdfDocument\(.*?\n        }\n\n        function reportPdfError",
            SOURCE,
            re.DOTALL,
        )
        self.assertIsNotNone(helper)
        helper_source = helper.group(0)
        self.assertIn("document.body.appendChild(pdfContainer)", helper_source)
        self.assertIn("await waitForPdfRender(pdfContainer)", helper_source)
        self.assertIn("pdfContainer.remove()", helper_source)

    def test_all_pdf_buttons_use_the_safe_export_helper(self):
        for function_name in (
            "downloadRankingPDF",
            "downloadArbitragePDF",
            "downloadBillPDF",
            "downloadRatesPDF",
            "downloadGuidePDF",
        ):
            self.assertRegex(SOURCE, rf"async function {function_name}\(\)")

        self.assertGreaterEqual(SOURCE.count("await savePdfDocument"), 5)
        self.assertNotIn("html2pdf().from(pdfContainer).set(opt)", SOURCE)

    def test_long_tables_have_a_mobile_canvas_safety_limit(self):
        self.assertIn("const dimensionScale = 20000 / contentHeight", SOURCE)
        self.assertIn("Math.sqrt(8000000 / (contentWidth * contentHeight))", SOURCE)
        self.assertIn("backgroundColor: '#ffffff'", SOURCE)


if __name__ == "__main__":
    unittest.main()
