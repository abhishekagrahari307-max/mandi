#!/usr/bin/env python3
"""Convert a user-supplied OGD-format CSV into a separate UP snapshot.

The input's origin cannot be verified by this script. It never changes the
verified feed, history or government-source snapshots.
"""
import argparse
import csv
import json
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

REQUIRED = ('State', 'District', 'Market', 'Commodity', 'Variety', 'Grade',
            'Arrival_Date', 'Min_x0020_Price', 'Max_x0020_Price', 'Modal_x0020_Price')


def convert(path: Path) -> dict:
    records = []
    skipped = 0
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        missing = set(REQUIRED) - set(reader.fieldnames or [])
        if missing:
            raise ValueError('Missing CSV columns: ' + ', '.join(sorted(missing)))
        for row in reader:
            if (row.get('State') or '').strip().casefold() != 'uttar pradesh':
                continue
            try:
                names = [(row.get(k) or '').strip() for k in ('District', 'Market', 'Commodity')]
                if not all(names):
                    raise ValueError('Missing market information')
                date = datetime.strptime((row.get('Arrival_Date') or '').strip(), '%d/%m/%Y').strftime('%Y-%m-%d')
                prices = []
                for key in ('Min_x0020_Price', 'Max_x0020_Price', 'Modal_x0020_Price'):
                    value = Decimal((row.get(key) or '').strip().replace(',', ''))
                    if not value.is_finite() or value <= 0:
                        raise ValueError('Invalid price')
                    prices.append(str(value))
                records.append(dict(district=names[0], market=names[1], commodity=names[2],
                                    variety=(row.get('Variety') or '').strip(), grade=(row.get('Grade') or '').strip(),
                                    arrival_date=date, min_price=prices[0], max_price=prices[1], modal_price=prices[2]))
            except (ValueError, InvalidOperation):
                skipped += 1
    if not records:
        raise ValueError('No valid Uttar Pradesh records; existing snapshot was not changed')
    return {'source': 'User-provided CSV; origin not independently verified', 'cross_verified': False,
            'imported_at': datetime.now(timezone.utc).isoformat(), 'records': records, 'skipped_up_rows': skipped}


def write_snapshot(payload: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=output.parent, delete=False) as handle:
            name = handle.name
            json.dump(payload, handle, ensure_ascii=False, separators=(',', ':'))
            handle.write('\n')
        os.chmod(name, 0o644)
        os.replace(name, output)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--output', type=Path, default=Path('data/uploaded_prices.json'))
    args = parser.parse_args()
    payload = convert(args.csv)
    write_snapshot(payload, args.output)
    print(f"Imported {len(payload['records'])} UP rows; skipped {payload['skipped_up_rows']} invalid UP rows.")


if __name__ == '__main__':
    main()
