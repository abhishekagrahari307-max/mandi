#!/usr/bin/env python3
"""Build the compact, browser-safe dashboard snapshot.

``data/latest.json`` and ``data/source_prices.json`` are the canonical backend
snapshots. They repeat the same 8,000+ price rows several times and are far too
large to parse on every mobile page load. GitHub Pages only needs one small,
column-encoded snapshot that preserves every field used by the UI.

The generated ``data/dashboard.json`` contains:

* one dictionary-encoded copy of every distinct price row,
* one dictionary-encoded copy of every distinct source/verification signature,
* lightweight ``[base_id, meta_id]`` references for the verified table and each
  official feed.

The browser expands those references into normal record objects on load, so the
existing dashboard functions do not need to know about the compact schema.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LATEST_PATH = DATA_DIR / "latest.json"
SOURCE_PRICES_PATH = DATA_DIR / "source_prices.json"
OUTPUT_PATH = DATA_DIR / "dashboard.json"

# Fields shared by the verified rows and every single-source feed row.
BASE_FIELDS = [
    "state",
    "district",
    "district_hi",
    "district_reported",
    "mandi",
    "mandi_hi",
    "commodity",
    "commodity_hi",
    "variety",
    "variety_hi",
    "grade",
    "grade_hi",
    "arrivals",
    "arrivals_unit",
    "arrivals_unit_hi",
    "min_price",
    "max_price",
    "modal_price",
    "price_unit",
    "arrival_date",
]

# Fields that describe the source of a row and its verification result.
META_FIELDS = [
    "source",
    "source_id",
    "source_reported",
    "verified",
    "cross_verified",
    "multi_source_verified",
    "three_source_verified",
    "verification_count",
    "verification_level",
    "verification_sources",
]


class ColumnEncoder:
    """Dictionary-encode one field at a time, preserving nulls and JSON types."""

    def __init__(self, fields: list[str]):
        self.fields = fields
        self.dictionaries: dict[str, list[Any]] = {field: [] for field in fields}
        self._indexes: dict[str, dict[str, int]] = {field: {} for field in fields}

    def encode(self, record: dict[str, Any], fields: list[str]) -> tuple[int, ...]:
        row: list[int] = []
        for field in fields:
            value = record.get(field)
            key = json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            field_index = self._indexes[field]
            index = field_index.get(key)
            if index is None:
                index = len(self.dictionaries[field])
                field_index[key] = index
                self.dictionaries[field].append(value)
            row.append(index)
        return tuple(row)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        os.chmod(tmp_name, 0o644)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def record_fields(records: Iterable[Any]) -> list[str]:
    keys: set[str] = set()
    for record in records:
        if isinstance(record, dict):
            keys.update(record.keys())
    extra = sorted(keys - set(BASE_FIELDS) - set(META_FIELDS))
    return META_FIELDS + extra


def all_source_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for feed in payload.get("feeds") or []:
        if isinstance(feed, dict):
            rows.extend(record for record in feed.get("records") or [] if isinstance(record, dict))
    return rows


def build_snapshot() -> dict[str, Any]:
    latest = read_json(LATEST_PATH)
    source_prices = read_json(SOURCE_PRICES_PATH)
    if not isinstance(latest, dict) or not isinstance(source_prices, dict):
        raise ValueError("latest.json and source_prices.json must contain JSON objects")

    latest_records = [r for r in latest.get("records") or [] if isinstance(r, dict)]
    feeds = [f for f in source_prices.get("feeds") or [] if isinstance(f, dict)]
    feed_records = [
        [r for r in feed.get("records") or [] if isinstance(r, dict)]
        for feed in feeds
    ]

    meta_fields = record_fields(
        [*latest_records, *all_source_records(source_prices)]
    )
    encoder = ColumnEncoder(BASE_FIELDS + meta_fields)
    base_ids: dict[tuple[int, ...], int] = {}
    meta_ids: dict[tuple[int, ...], int] = {}
    base_rows: list[list[int]] = []
    meta_rows: list[list[int]] = []

    def encode_dataset(records: list[dict[str, Any]]) -> list[list[int]]:
        entries: list[list[int]] = []
        for record in records:
            base_row = encoder.encode(record, BASE_FIELDS)
            meta_row = encoder.encode(record, meta_fields)
            base_id = base_ids.get(base_row)
            if base_id is None:
                base_id = len(base_rows)
                base_ids[base_row] = base_id
                base_rows.append(list(base_row))
            meta_id = meta_ids.get(meta_row)
            if meta_id is None:
                meta_id = len(meta_rows)
                meta_ids[meta_row] = meta_id
                meta_rows.append(list(meta_row))
            entries.append([base_id, meta_id])
        return entries

    latest_meta = {
        key: value for key, value in latest.items() if key != "records"
    }
    latest_meta["record_count"] = len(latest_records)
    latest_meta["entries"] = encode_dataset(latest_records)

    source_meta = {
        key: value for key, value in source_prices.items() if key != "feeds"
    }
    compact_feeds: list[dict[str, Any]] = []
    for feed, records in zip(feeds, feed_records):
        compact_feed = {
            key: value for key, value in feed.items() if key != "records"
        }
        compact_feed["record_count"] = len(records)
        compact_feed["entries"] = encode_dataset(records)
        compact_feeds.append(compact_feed)
    source_meta["feeds"] = compact_feeds

    return {
        "schema_version": 1,
        "generated_at": latest.get("updated_at") or latest.get("last_checked_at"),
        "fields": {"base": BASE_FIELDS, "meta": meta_fields},
        "dictionaries": encoder.dictionaries,
        "rows": {"base": base_rows, "meta": meta_rows},
        "latest": latest_meta,
        "source_prices": source_meta,
    }


def decode_entry(snapshot: dict[str, Any], entry: list[int]) -> dict[str, Any]:
    base_id, meta_id = entry
    record: dict[str, Any] = {}
    dictionaries = snapshot["dictionaries"]
    for field, value_id in zip(snapshot["fields"]["base"], snapshot["rows"]["base"][base_id]):
        record[field] = dictionaries[field][value_id]
    for field, value_id in zip(snapshot["fields"]["meta"], snapshot["rows"]["meta"][meta_id]):
        record[field] = dictionaries[field][value_id]
    return record


def verify_snapshot(snapshot: dict[str, Any]) -> int:
    """Reconstruct every row and compare it with the canonical JSON files."""
    latest = read_json(LATEST_PATH)
    source_prices = read_json(SOURCE_PRICES_PATH)
    checked = 0

    def compare(entries: list[list[int]], original: list[dict[str, Any]], label: str) -> None:
        nonlocal checked
        if len(entries) != len(original):
            raise ValueError(f"{label}: {len(entries)} entries for {len(original)} source rows")
        for index, (entry, expected) in enumerate(zip(entries, original)):
            actual = decode_entry(snapshot, entry)
            if actual != expected:
                raise ValueError(f"{label}: row {index} does not match its source snapshot")
            checked += 1

    compare(snapshot["latest"]["entries"], latest.get("records") or [], "latest")
    compact_feeds = snapshot["source_prices"]["feeds"]
    original_feeds = source_prices.get("feeds") or []
    if len(compact_feeds) != len(original_feeds):
        raise ValueError("dashboard feed count does not match source_prices.json")
    for compact_feed, original_feed in zip(compact_feeds, original_feeds):
        compare(
            compact_feed["entries"],
            original_feed.get("records") or [],
            f"feed:{compact_feed.get('id', '?')}",
        )
    return checked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="verify the existing dashboard.json against the canonical snapshots",
    )
    args = parser.parse_args(argv)

    if args.verify:
        snapshot = read_json(OUTPUT_PATH)
    else:
        snapshot = build_snapshot()
        write_json_atomic(OUTPUT_PATH, snapshot)

    checked = verify_snapshot(snapshot)
    original_bytes = LATEST_PATH.stat().st_size + SOURCE_PRICES_PATH.stat().st_size
    compact_bytes = OUTPUT_PATH.stat().st_size
    reduction = 100 * (1 - compact_bytes / original_bytes) if original_bytes else 0
    print(
        f"Verified {checked:,} price rows; dashboard.json is {compact_bytes:,} bytes "
        f"({reduction:.1f}% smaller than {original_bytes:,} bytes of canonical JSON)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
