#!/usr/bin/env python3
"""Automated web scraper for AGMARKNET, e-NAM, UP e-Mandi data.

Fetches mandi prices from publicly accessible aggregator websites that
source data from official government portals (AGMARKNET, e-NAM, UP e-Mandi).

Runs in GitHub Actions every 6 hours to keep data fresh.
"""

import json
import re
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
DATA_DIR = Path("data")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Priority commodities for scraping
PRIORITY_COMMODITIES = [
    "wheat", "rice", "potato", "onion", "tomato",
    "maize", "paddy", "mustard", "gram", "arhar"
]


def fetch_url(url: str, timeout: int = 30) -> str:
    """Fetch URL content with browser-like headers."""
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    req = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  ⚠ Failed to fetch {url}: {e}")
        return ""


def parse_mandipulse_table(html: str, commodity: str, date_str: str) -> list[dict]:
    """Parse mandi price table from mandipulse.com HTML."""
    records = []
    # Find table rows with mandi data
    # Pattern: | Mandi Name | District | Min | Modal | Max |
    row_pattern = re.compile(
        r'\|\s*\[?[^|\]]*?(?:mandi|APMC|price|bhav|rate)[^|\]]*\]?\([^)]*\)\s*\|\s*'
        r'([^|]+)\s*\|\s*₹([\d,]+)\s*\|\s*\*?\*?₹([\d,]+)\*?\*?\s*\|\s*₹([\d,]+)\s*\|',
        re.IGNORECASE
    )
    
    for match in row_pattern.finditer(html):
        district = match.group(1).strip()
        min_price = int(match.group(2).replace(",", ""))
        modal_price = int(match.group(3).replace(",", ""))
        max_price = int(match.group(4).replace(",", ""))
        
        # Extract mandi name from the link text
        mandi_match = re.search(
            r'\[([^\]]*(?:APMC|mandi)[^\]]*)\]',
            match.group(0), re.IGNORECASE
        )
        mandi_name = mandi_match.group(1).strip() if mandi_match else f"{district} APMC"
        # Clean mandi name
        mandi_name = re.sub(r'\s*(mandi\s*bhav|mandi\s*rate|price\s*in|rate)\s*', ' ', mandi_name, flags=re.IGNORECASE).strip()
        
        records.append({
            "state": "Uttar Pradesh",
            "district": district,
            "market": mandi_name if "APMC" in mandi_name else f"{mandi_name} APMC",
            "commodity": commodity,
            "variety": "Other",
            "grade": "FAQ",
            "min_price": min_price,
            "max_price": max_price,
            "modal_price": modal_price,
            "arrival_date": date_str,
            "verification_count": 1,
            "cross_verified": False,
            "three_source_verified": False,
            "multi_source_verified": False,
            "verification_level": "single_source",
            "source": "AGMARKNET (Web Scraped)",
            "source_id": "agmarknet",
        })
    
    return records


def scrape_mandipulse(commodities: list[str] = None) -> list[dict]:
    """Scrape UP mandi prices from mandipulse.com for priority commodities."""
    if commodities is None:
        commodities = PRIORITY_COMMODITIES
    
    all_records = []
    today = datetime.now(IST).strftime("%d/%m/%Y")
    
    for commodity in commodities:
        url = f"https://mandipulse.com/mandi-bhav/uttar-pradesh/{commodity}"
        print(f"  Fetching {commodity} from mandipulse.com...")
        html = fetch_url(url)
        if not html:
            continue
        
        records = parse_mandipulse_table(html, commodity.title(), today)
        if records:
            print(f"    ✅ {commodity}: {len(records)} mandis")
            all_records.extend(records)
        else:
            print(f"    ⚠ {commodity}: no records parsed")
    
    return all_records


def update_source_prices(new_records: list[dict]):
    """Merge new records into source_prices.json."""
    sp_path = DATA_DIR / "source_prices.json"
    if not sp_path.exists():
        print("  ⚠ source_prices.json not found, skipping merge")
        return
    
    with open(sp_path) as f:
        sp = json.load(f)
    
    iso_now = datetime.now(IST).isoformat()
    
    # Find or create agmarknet feed
    agmarknet_feed = None
    for feed in sp.get("feeds", []):
        if feed["id"] == "agmarknet":
            agmarknet_feed = feed
            break
    
    if not agmarknet_feed:
        agmarknet_feed = {
            "id": "agmarknet",
            "name": "AGMARKNET (Web Scraped)",
            "name_hi": "AGMARKNET (वेब स्क्रैप्ड)",
            "source_url": "https://agmarknet.gov.in/",
            "status": "cached",
            "records": [],
        }
        sp.setdefault("feeds", []).append(agmarknet_feed)
    
    # Deduplicate and merge
    existing = agmarknet_feed.get("records", [])
    seen = {(r.get("district",""), r.get("market",""), r.get("commodity","")) for r in existing}
    added = 0
    for r in new_records:
        key = (r.get("district",""), r.get("market",""), r.get("commodity",""))
        if key not in seen:
            existing.append(r)
            seen.add(key)
            added += 1
    
    agmarknet_feed["records"] = existing
    agmarknet_feed["status"] = "cached"
    agmarknet_feed["latest_check_status"] = "ok"
    agmarknet_feed["data_updated_at"] = iso_now
    agmarknet_feed["total_record_count"] = len(existing)
    agmarknet_feed["stored_record_count"] = len(existing)
    agmarknet_feed["records_truncated"] = False
    agmarknet_feed["message"] = f"Auto-scraped {len(existing)} records from mandipulse.com (AGMARKNET aggregator)"
    
    with open(sp_path, "w") as f:
        json.dump(sp, f, indent=2, ensure_ascii=False)
    
    print(f"\n  ✅ AGMARKNET feed updated: +{added} new, {len(existing)} total")


def main():
    print("=" * 60)
    print("  🤖 Automated Mandi Data Scraper")
    print(f"  {datetime.now(IST).strftime('%d %b %Y, %I:%M %p IST')}")
    print("=" * 60)
    
    print("\n📡 Scraping mandipulse.com (AGMARKNET aggregator)...")
    records = scrape_mandipulse()
    
    if records:
        print(f"\n📊 Total scraped: {len(records)} records")
        commodities = set(r["commodity"] for r in records)
        districts = set(r["district"] for r in records)
        print(f"   Commodities: {len(commodities)} — {sorted(commodities)}")
        print(f"   Districts: {len(districts)}")
        
        update_source_prices(records)
    else:
        print("\n  ⚠ No records scraped — keeping existing data")
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
