#!/usr/bin/env python3
"""Publish the official mandi snapshots as spreadsheet-ready CSV feeds.

Google Sheets (``=IMPORTDATA``) and Excel (``Data -> From Web`` / Power Query)
can both read a plain CSV URL and refresh it on a timer. This module converts
the JSON snapshots produced by ``update_data.py`` into stable, flat CSV tables
inside ``data/sheets/`` so a spreadsheet always shows the latest published
government prices without any manual copy-paste.

Design rules that follow the rest of this project:

* No value is invented here. Every cell is copied from an existing snapshot in
  ``data/``; empty feeds produce a header-only CSV rather than filler rows.
* Every cell is written through :func:`csv_safe`, so a government-supplied
  value starting with ``=``, ``+``, ``-`` or ``@`` can never be executed as a
  formula by Excel, Google Sheets or LibreOffice.
* The CSV writer (not f-strings) handles quoting, so mandi and commodity names
  containing commas stay in their own column.
"""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


DATA_DIR = Path("data")
SHEETS_DIRNAME = "sheets"
# Public base URL of the GitHub Pages deployment. A spreadsheet formula needs an
# absolute URL, so the generated manifest and README snippets use this.
PUBLIC_BASE_URL = os.environ.get(
    "SHEETS_PUBLIC_BASE_URL",
    "https://abhishekagrahari307-max.github.io/mandi",
).rstrip("/")

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value: Any) -> str:
    """Return a cell that stays plain text in every spreadsheet application.

    A leading ``=``, ``+``, ``-``, ``@``, tab or carriage return makes Excel,
    Google Sheets and LibreOffice treat upstream text as a formula. Government
    feeds are untrusted input for this purpose, so such a value is prefixed with
    an apostrophe. ``None`` becomes an empty cell instead of the text "None".
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(item) for item in value if item not in (None, ""))
    text_value = str(value)
    if text_value[:1] in FORMULA_PREFIXES:
        return "'" + text_value
    return text_value


def rows_to_csv(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    """Render a header plus rows as RFC 4180 CSV text."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow([csv_safe(column) for column in header])
    for row in rows:
        writer.writerow([csv_safe(cell) for cell in row])
    return buffer.getvalue()


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, newline=""
    ) as handle:
        handle.write(text)
        temp_name = handle.name
    # NamedTemporaryFile creates 0600 files. These snapshots are published as
    # static assets, so give them the same world-readable mode as the rest of
    # data/ instead of leaving them owner-only.
    os.chmod(temp_name, 0o644)
    os.replace(temp_name, path)


# ---------------------------------------------------------------------------
# Individual sheet builders. Each returns (header, rows).
# ---------------------------------------------------------------------------

PRICE_HEADER = (
    "Date", "District", "जिला", "Mandi", "Commodity", "जिंस", "Variety", "Grade",
    "Min_Price", "Modal_Price", "Max_Price", "Unit",
    "Verified_By", "Source_Count", "Updated_At_IST",
)


def build_mandi_prices(latest: dict[str, Any]) -> tuple[Sequence[str], list[list[Any]]]:
    """Cross-verified UP mandi prices (the table shown on the dashboard)."""
    updated_at = latest.get("updated_at")
    rows = []
    for record in latest.get("records") or []:
        rows.append([
            record.get("arrival_date"),
            record.get("district"),
            record.get("district_hi"),
            record.get("mandi"),
            record.get("commodity"),
            record.get("commodity_hi"),
            record.get("variety"),
            record.get("grade"),
            record.get("min_price"),
            record.get("modal_price"),
            record.get("max_price"),
            record.get("price_unit") or "Quintal",
            record.get("verification_sources") or record.get("source"),
            record.get("verification_count"),
            updated_at,
        ])
    return PRICE_HEADER, rows


SOURCE_PRICE_HEADER = (
    "Feed", "Feed_Status", "Date", "District", "Mandi", "Commodity", "Variety",
    "Grade", "Min_Price", "Modal_Price", "Max_Price", "Unit", "Verification",
    "Feed_Updated_At", "Source_URL",
)


def build_source_prices(source_prices: dict[str, Any]) -> tuple[Sequence[str], list[list[Any]]]:
    """Every government feed kept separate — never averaged or merged."""
    rows = []
    for feed in source_prices.get("feeds") or []:
        feed_name = feed.get("name")
        feed_status = feed.get("status")
        feed_updated = feed.get("data_updated_at")
        source_url = feed.get("source_url")
        for record in feed.get("records") or []:
            rows.append([
                feed_name,
                feed_status,
                record.get("arrival_date"),
                record.get("district"),
                record.get("mandi"),
                record.get("commodity"),
                record.get("variety"),
                record.get("grade"),
                record.get("min_price"),
                record.get("modal_price"),
                record.get("max_price"),
                record.get("price_unit") or "Quintal",
                record.get("verification_label") or "single_source",
                feed_updated,
                source_url,
            ])
    return SOURCE_PRICE_HEADER, rows


STATE_HEADER = (
    "State", "Districts", "Mandis", "Records", "Average_Modal_Price",
    "Minimum_Price", "Maximum_Price", "Top_Commodity", "Updated_At_IST",
)


def build_state_prices(state_prices: dict[str, Any]) -> tuple[Sequence[str], list[list[Any]]]:
    updated_at = state_prices.get("updated_at")
    rows = []
    for state in state_prices.get("states") or []:
        rows.append([
            state.get("state"),
            state.get("district_count"),
            state.get("mandi_count"),
            state.get("record_count"),
            state.get("average_modal_price"),
            state.get("minimum_price"),
            state.get("maximum_price"),
            state.get("top_commodity"),
            updated_at,
        ])
    return STATE_HEADER, rows


DIRECTORY_HEADER = (
    "State", "Division", "District", "जिला", "Mandi", "Grade", "Secretary",
    "CUG_Number", "Commodities", "Latest_Price_Date", "Min_Modal_Price",
    "Max_Modal_Price", "Contacts", "Map_URL", "Source_URL",
)


def build_mandi_directory(mandis: dict[str, Any]) -> tuple[Sequence[str], list[list[Any]]]:
    rows = []
    for mandi in mandis.get("mandis") or []:
        contacts = [
            " ".join(
                str(part) for part in (contact.get("name"), contact.get("phone")) if part
            )
            for contact in mandi.get("contacts") or []
            if isinstance(contact, dict)
        ]
        rows.append([
            mandi.get("state"),
            mandi.get("division"),
            mandi.get("district"),
            mandi.get("district_hi"),
            mandi.get("mandi"),
            mandi.get("grade"),
            mandi.get("secretary"),
            mandi.get("cug"),
            mandi.get("commodity_count"),
            mandi.get("latest_price_date"),
            mandi.get("minimum_modal_price"),
            mandi.get("maximum_modal_price"),
            contacts or (mandi.get("central_helpdesk") or []),
            mandi.get("map_url"),
            mandi.get("directory_source_url"),
        ])
    return DIRECTORY_HEADER, rows


HISTORY_HEADER = ("Commodity", "Date", "Average_Modal_Price")


def build_price_history(history: dict[str, Any]) -> tuple[Sequence[str], list[list[Any]]]:
    """Long-format history so a spreadsheet can pivot or chart it directly."""
    rows = []
    for commodity in sorted(history or {}):
        for point in history.get(commodity) or []:
            if not isinstance(point, dict):
                continue
            rows.append([commodity, point.get("date"), point.get("price")])
    return HISTORY_HEADER, rows


SOURCE_STATUS_HEADER = (
    "Source", "Status", "Records", "Message", "URL", "Last_Checked_At_IST",
)


def build_source_status(sources: dict[str, Any]) -> tuple[Sequence[str], list[list[Any]]]:
    checked_at = sources.get("last_checked_at")
    rows = []
    for source in sources.get("sources") or []:
        rows.append([
            source.get("name"),
            source.get("status"),
            source.get("records"),
            source.get("message"),
            source.get("url"),
            checked_at,
        ])
    return SOURCE_STATUS_HEADER, rows


STATUS_HEADER = ("Field", "Value")


def build_update_status(
    latest: dict[str, Any],
    sources: dict[str, Any],
    counts: dict[str, int],
) -> tuple[Sequence[str], list[list[Any]]]:
    """One-glance metadata block for the top of a spreadsheet."""
    rows = [
        ["Prices updated at (IST)", latest.get("updated_at")],
        ["Portals last checked (IST)", latest.get("last_checked_at")],
        ["Published source", latest.get("source")],
        ["Cross-verified", latest.get("verified")],
        ["Minimum matching feeds", latest.get("minimum_price_source_matches")],
        ["Connected price feeds", latest.get("connected_price_sources")],
        ["Update frequency", latest.get("update_frequency") or sources.get("update_frequency")],
        ["Daily update slots (IST)", latest.get("update_slots_ist") or sources.get("update_slots_ist")],
        ["Verified price rows", counts.get("mandi_prices", 0)],
        ["Single-source price rows", counts.get("source_prices", 0)],
        ["State summary rows", counts.get("state_prices", 0)],
        ["Mandi directory rows", counts.get("mandi_directory", 0)],
        ["History points", counts.get("price_history", 0)],
        ["Data policy", sources.get("policy")],
    ]
    return STATUS_HEADER, rows


# ``id`` -> (filename, human label, builder key)
SHEET_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "mandi_prices",
        "file": "mandi_prices.csv",
        "title_en": "Cross-verified UP mandi prices",
        "title_hi": "सत्यापित यूपी मंडी भाव",
    },
    {
        "id": "source_prices",
        "file": "source_prices.csv",
        "title_en": "Prices reported by each government feed (single-source)",
        "title_hi": "हर सरकारी feed के अलग भाव (single-source)",
    },
    {
        "id": "state_prices",
        "file": "state_prices.csv",
        "title_en": "State-wise price summary",
        "title_hi": "राज्य-वार भाव सारांश",
    },
    {
        "id": "mandi_directory",
        "file": "mandi_directory.csv",
        "title_en": "Mandi directory with secretary and CUG contact",
        "title_hi": "मंडी निर्देशिका (सचिव एवं सी.यू.जी सम्पर्क)",
    },
    {
        "id": "price_history",
        "file": "price_history.csv",
        "title_en": "Verified price history (long format)",
        "title_hi": "सत्यापित भाव इतिहास",
    },
    {
        "id": "source_status",
        "file": "source_status.csv",
        "title_en": "Government portal health for each refresh",
        "title_hi": "हर सरकारी पोर्टल की स्थिति",
    },
    {
        "id": "update_status",
        "file": "update_status.csv",
        "title_en": "Last update time and record counts",
        "title_hi": "अंतिम अपडेट समय और गिनती",
    },
)


def build_sheets(data_dir: Path = DATA_DIR) -> dict[str, dict[str, Any]]:
    """Build every spreadsheet table from the JSON snapshots in ``data_dir``."""
    data_dir = Path(data_dir)
    latest = read_json(data_dir / "latest.json", {}) or {}
    source_prices = read_json(data_dir / "source_prices.json", {}) or {}
    state_prices = read_json(data_dir / "state_prices.json", {}) or {}
    mandis = read_json(data_dir / "mandis.json", {}) or {}
    history = read_json(data_dir / "history.json", {}) or {}
    sources = read_json(data_dir / "sources.json", {}) or {}

    builders: dict[str, Callable[[], tuple[Sequence[str], list[list[Any]]]]] = {
        "mandi_prices": lambda: build_mandi_prices(latest),
        "source_prices": lambda: build_source_prices(source_prices),
        "state_prices": lambda: build_state_prices(state_prices),
        "mandi_directory": lambda: build_mandi_directory(mandis),
        "price_history": lambda: build_price_history(history),
        "source_status": lambda: build_source_status(sources),
    }

    built: dict[str, dict[str, Any]] = {}
    for sheet_id, builder in builders.items():
        header, rows = builder()
        built[sheet_id] = {"header": header, "rows": rows}

    counts = {sheet_id: len(value["rows"]) for sheet_id, value in built.items()}
    header, rows = build_update_status(latest, sources, counts)
    built["update_status"] = {"header": header, "rows": rows}
    return built


def sheet_csv(sheet_id: str, data_dir: Path = DATA_DIR) -> str:
    """Render one sheet as CSV text (used by the API and the file writer)."""
    built = build_sheets(data_dir)
    if sheet_id not in built:
        raise KeyError(sheet_id)
    table = built[sheet_id]
    return rows_to_csv(table["header"], table["rows"])


def build_manifest(built: dict[str, dict[str, Any]], latest: dict[str, Any]) -> dict[str, Any]:
    sheets = []
    for spec in SHEET_SPECS:
        table = built.get(spec["id"], {"rows": [], "header": ()})
        csv_url = f"{PUBLIC_BASE_URL}/data/{SHEETS_DIRNAME}/{spec['file']}"
        sheets.append({
            "id": spec["id"],
            "file": spec["file"],
            "title_en": spec["title_en"],
            "title_hi": spec["title_hi"],
            "row_count": len(table["rows"]),
            "columns": list(table["header"]),
            "csv_url": csv_url,
            "relative_path": f"data/{SHEETS_DIRNAME}/{spec['file']}",
            "google_sheets_formula": f'=IMPORTDATA("{csv_url}")',
            "excel_power_query": build_power_query(spec["id"], csv_url),
        })
    return {
        "title_en": "Auto-updating spreadsheet feeds for the UP Mandi dashboard",
        "title_hi": "यूपी मंडी डैशबोर्ड की स्वतः-अपडेट स्प्रेडशीट फीड",
        "generated_at": latest.get("last_checked_at"),
        "prices_updated_at": latest.get("updated_at"),
        "update_frequency": latest.get("update_frequency") or "4 times daily",
        "update_slots_ist": latest.get("update_slots_ist") or ["06:30", "12:30", "16:30", "20:30"],
        "base_url": f"{PUBLIC_BASE_URL}/data/{SHEETS_DIRNAME}/",
        "usage_google_sheets": (
            "Paste the google_sheets_formula of any sheet into cell A1 of a "
            "Google Sheet. Sheets re-fetches IMPORTDATA roughly every hour and "
            "on every file open."
        ),
        "usage_excel": (
            "Excel: Data -> From Web -> paste csv_url -> Load, then Query "
            "Properties -> Refresh every N minutes / Refresh data when opening."
        ),
        "policy": (
            "Every cell is copied from an official government snapshot. No "
            "simulated prices, arrivals or contacts are generated."
        ),
        "sheets": sheets,
    }


def build_power_query(sheet_id: str, csv_url: str) -> str:
    """Return an Excel Power Query (M) script for one CSV feed.

    Pasting this into Excel's *Advanced Editor* creates a live connection that
    Excel can refresh on a timer, which is the only Excel mechanism that keeps
    a workbook current without a macro.
    """
    return (
        "let\n"
        f'    Source = Csv.Document(Web.Contents("{csv_url}"),\n'
        "        [Delimiter = \",\", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),\n"
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])\n"
        "in\n"
        "    Promoted"
    )


def write_all(data_dir: Path = DATA_DIR) -> dict[str, int]:
    """Write every CSV plus the manifest, returning row counts per sheet."""
    data_dir = Path(data_dir)
    out_dir = data_dir / SHEETS_DIRNAME
    out_dir.mkdir(parents=True, exist_ok=True)

    built = build_sheets(data_dir)
    counts: dict[str, int] = {}
    for spec in SHEET_SPECS:
        table = built[spec["id"]]
        write_text_atomic(out_dir / spec["file"], rows_to_csv(table["header"], table["rows"]))
        counts[spec["id"]] = len(table["rows"])

    latest = read_json(data_dir / "latest.json", {}) or {}
    manifest = build_manifest(built, latest)
    write_text_atomic(
        out_dir / "index.json",
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    return counts


def main() -> None:
    counts = write_all()
    summary = ", ".join(f"{name}={count}" for name, count in counts.items())
    print(f"Spreadsheet feeds written to data/{SHEETS_DIRNAME}/ ({summary})")


if __name__ == "__main__":
    main()
