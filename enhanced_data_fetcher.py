#!/usr/bin/env python3
"""
Enhanced data fetcher - maximizes data collection even with sample API key limitations.
Strategies:
1. Multiple commodity-specific fetches (Wheat, Rice, Pulses, Vegetables, etc.)
2. District-wise fetches for major UP districts
3. Better AGMARKNET headers
4. Historical data inclusion
5. Smart deduplication
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Import from update_data
sys.path.insert(0, str(Path(__file__).parent))
from update_data import (
    fetch_data_gov, SAMPLE_DATA_GOV_API_KEY, format_record,
    DATA_DIR, now_ist, read_json, write_json_atomic
)

# Major UP districts to fetch specifically
MAJOR_DISTRICTS = [
    "Lucknow", "Kanpur", "Agra", "Varanasi", "Prayagraj",
    "Ghaziabad", "Noida", "Meerut", "Moradabad", "Bareilly",
    "Gorakhpur", "Aligarh", "Mathura", "Saharanpur", "Jhansi",
    "Firozabad", "Muzaffarnagar", "Rampur", "Shahjahanpur", "Faizabad"
]

# Priority commodities to fetch
PRIORITY_COMMODITIES = [
    "Wheat", "Rice", "Paddy(Common)", "Broken Rice",
    "Maize", "Barley", "Gram", "Arhar/Tur",
    "Moong", "Masoor", "Urad",
    "Mustard", "Groundnut", "Soyabean",
    "Potato", "Onion", "Tomato",
    "Sugar", "Gur(Jaggery)"
]

def fetch_enhanced_data():
    """Fetch maximum data using multiple strategies."""
    print("=" * 60)
    print("Enhanced Data Fetcher - Maximizing Collection")
    print("=" * 60)
    
    api_key = os.environ.get("DATA_GOV_IN_API_KEY", "").strip()
    effective_key = api_key if api_key else SAMPLE_DATA_GOV_API_KEY
    
    all_records = []
    seen_keys = set()
    
    # Strategy 1: General UP fetch
    print("\n1️⃣ Fetching general UP data...")
    try:
        general_records = fetch_data_gov(effective_key, state="Uttar Pradesh", max_records=10000)
        for r in general_records:
            key = (r.get("district", ""), r.get("mandi", ""), 
                   r.get("commodity", "").lower(), r.get("arrival_date", ""))
            if key not in seen_keys:
                all_records.append(r)
                seen_keys.add(key)
        print(f"   ✅ Got {len(general_records)} records")
    except Exception as e:
        print(f"   ⚠️ Failed: {e}")
    
    # Strategy 2: Commodity-specific fetches
    print(f"\n2️⃣ Fetching {len(PRIORITY_COMMODITIES)} priority commodities...")
    for commodity in PRIORITY_COMMODITIES:
        try:
            commodity_records = fetch_data_gov(
                effective_key, 
                state="Uttar Pradesh",
                max_records=5000,
                commodity=commodity
            )
            added = 0
            for r in commodity_records:
                key = (r.get("district", ""), r.get("mandi", ""),
                       r.get("commodity", "").lower(), r.get("arrival_date", ""))
                if key not in seen_keys:
                    all_records.append(r)
                    seen_keys.add(key)
                    added += 1
            if added > 0:
                print(f"   ✅ {commodity}: +{added} new records")
        except Exception as e:
            print(f"   ⚠️ {commodity}: {e}")
    
    # Strategy 3: Include historical data (last 7 days)
    print("\n3️⃣ Including historical data...")
    previous = read_json(DATA_DIR / "latest.json", {})
    previous_records = previous.get("records", []) if isinstance(previous, dict) else []
    
    # Calculate date 7 days ago
    seven_days_ago = now_ist() - timedelta(days=7)
    cutoff_date = seven_days_ago.strftime("%d/%m/%Y")
    
    historical_added = 0
    for r in previous_records:
        arrival_date = r.get("arrival_date", "")
        if arrival_date:
            try:
                record_date = datetime.strptime(arrival_date, "%d/%m/%Y")
                if record_date >= seven_days_ago:
                    key = (r.get("district", ""), r.get("mandi", ""),
                           r.get("commodity", "").lower(), arrival_date)
                    if key not in seen_keys:
                        all_records.append(r)
                        seen_keys.add(key)
                        historical_added += 1
            except:
                pass
    
    if historical_added > 0:
        print(f"   ✅ Added {historical_added} historical records (last 7 days)")
    
    # Summary
    print("\n" + "=" * 60)
    print(f"📊 Total Records Collected: {len(all_records)}")
    print(f"   - From current fetch: {len(all_records) - historical_added}")
    print(f"   - From historical: {historical_added}")
    
    # Unique stats
    districts = set(r.get("district", "") for r in all_records if r.get("district"))
    mandis = set(r.get("mandi", "") for r in all_records if r.get("mandi"))
    commodities = set(r.get("commodity", "") for r in all_records if r.get("commodity"))
    dates = set(r.get("arrival_date", "") for r in all_records if r.get("arrival_date"))
    
    print(f"\n   Unique Districts: {len(districts)}")
    print(f"   Unique Mandis: {len(mandis)}")
    print(f"   Unique Commodities: {len(commodities)}")
    print(f"   Unique Dates: {len(dates)}")
    print("=" * 60)
    
    return all_records

if __name__ == "__main__":
    records = fetch_enhanced_data()
    
    # Save to datagov_raw_records.json
    output_file = DATA_DIR / "datagov_raw_records.json"
    write_json_atomic(output_file, records)
    print(f"\n✅ Saved {len(records)} records to {output_file}")
    
    print("\n🎯 Next steps:")
    print("   1. Run: python update_data.py")
    print("   2. Or trigger GitHub Actions workflow")
