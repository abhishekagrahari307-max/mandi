#!/usr/bin/env python3
"""Refresh the dashboard from official market-data sources.

The pipeline deliberately does not manufacture prices, arrivals, contacts, or
auction bids. When an upstream source is unavailable it keeps the last verified
snapshot and records the failed check in data/sources.json.
"""

from __future__ import annotations

import html
import json
import os
import re
import tempfile
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DATA_DIR = Path("data")
IST = ZoneInfo("Asia/Kolkata")
DATA_GOV_RESOURCE_ID = os.environ.get(
    "DATA_GOV_RESOURCE_ID", "9ef84268-d588-465a-a308-a864a43d0070"
)
DATA_GOV_API = f"https://api.data.gov.in/resource/{DATA_GOV_RESOURCE_ID}"
AGMARKNET_URL = (
    "https://agmarknet.gov.in/SearchCmmMkt.aspx?Tx_Commodity=0&Tx_State=UP"
    "&Tx_District=0&Tx_Market=0&Tx_Trend=0"
)
EMANDI_CONTACT_URLS = (
    "https://emandi.up.gov.in/MandiHome/Contactus",
    "https://www.emanditraining.in/MandiHome/Contactus",
)
ENAM_PORTAL_URL = "https://www.enam.gov.in/web/"
ENAM_TRADE_URL = "https://enam.gov.in/web/dashboard/trade-data"
UPDATE_SLOTS_IST = ("00:30", "04:30", "08:30", "12:30", "16:30", "20:30")
USER_AGENT = "UP-Mandi-Dashboard/4.0 (+https://github.com/abhishekagrahari307-max/mandi)"

DISTRICT_HI = {
    "Agra": "आगरा", "Aligarh": "अलीगढ़", "Ambedkar Nagar": "अम्बेडकर नगर",
    "Amethi": "अमेठी", "Amroha": "अमरोहा", "Auraiya": "औरैया",
    "Azamgarh": "आजमगढ़", "Baghpat": "बागपत", "Bahraich": "बहराइच",
    "Ballia": "बलिया", "Balrampur": "बलरामपुर", "Banda": "बांदा",
    "Barabanki": "बाराबंकी", "Bareilly": "बरेली", "Basti": "बस्ती",
    "Bhadohi": "भदोही", "Bijnor": "बिजनौर", "Budaun": "बदायूं",
    "Bulandshahr": "बुलंदशहर", "Chandauli": "चंदौली", "Chitrakoot": "चित्रकूट",
    "Deoria": "देवरिया", "Etah": "एटा", "Etawah": "इटावा",
    "Ayodhya": "अयोध्या", "Farrukhabad": "फर्रुखाबाद", "Fatehpur": "फतेहपुर",
    "Firozabad": "फिरोजाबाद", "Gautam Buddha Nagar": "गौतम बुद्ध नगर",
    "Ghaziabad": "गाजियाबाद", "Ghazipur": "गाजीपुर", "Gonda": "गोंडा",
    "Gorakhpur": "गोरखपुर", "Hamirpur": "हमीरपुर", "Hapur": "हापुड़",
    "Hardoi": "हरदोई", "Hathras": "हाथरस", "Jalaun": "जालौन",
    "Jaunpur": "जौनपुर", "Jhansi": "झांसी", "Kannauj": "कन्नौज",
    "Kanpur Dehat": "कानपुर देहात", "Kanpur Nagar": "कानपुर नगर",
    "Kasganj": "कासगंज", "Kaushambi": "कौशाम्बी", "Kushinagar": "कुशीनगर",
    "Lakhimpur Kheri": "लखीमपुर खीरी", "Lalitpur": "ललितपुर", "Lucknow": "लखनऊ",
    "Maharajganj": "महाराजगंज", "Mahoba": "महोबा", "Mainpuri": "मैनपुरी",
    "Mathura": "मथुरा", "Mau": "मऊ", "Meerut": "मेरठ",
    "Mirzapur": "मिर्जापुर", "Moradabad": "मुरादाबाद", "Muzaffarnagar": "मुजफ्फरनगर",
    "Pilibhit": "पीलीभीत", "Pratapgarh": "प्रतापगढ़", "Prayagraj": "प्रयागराज",
    "Raebareli": "रायबरेली", "Rampur": "रामपुर", "Saharanpur": "सहारनपुर",
    "Sambhal": "संभल", "Sant Kabir Nagar": "संत कबीर नगर",
    "Shahjahanpur": "शाहजहाँपुर", "Shamli": "शामली", "Shravasti": "श्रावस्ती",
    "Siddharthnagar": "सिद्धार्थनगर", "Sitapur": "सीतापुर", "Sonbhadra": "सोनभद्र",
    "Sultanpur": "सुल्तानपुर", "Unnao": "उन्नाव", "Varanasi": "वाराणसी",
}

COMMODITY_HI = {
    "Wheat": "गेहूं", "Paddy(Common)": "धान (सामान्य)",
    "Paddy(Dhan)(Common)": "धान (सामान्य)", "Paddy(Basmati)": "धान (बासमती)",
    "Paddy(Dhan)(Basmati)": "धान (बासमती)", "Rice": "चावल", "Potato": "आलू",
    "Onion": "प्याज़", "Tomato": "टमाटर", "Mustard": "सरसों",
    "Bengal Gram(Gram)(Whole)": "चना", "Garlic": "लहसुन",
    "Arhar (Tur/Red Gram)(Whole)": "अरहर", "Green Chilli": "हरी मिर्च",
    "Maize": "मक्का", "Barley (Jau)": "जौ", "Barley(Jau)": "जौ",
    "Green Gram (Moong)(Whole)": "मूंग", "Black Gram (Urd Beans)(Whole)": "उड़द",
    "Ginger(Green)": "अदरक", "Apple": "सेब", "Banana": "केला",
}


class ContactTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_td = False
        self.cell_parts: list[str] = []
        self.row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "td":
            self.in_td = True
            self.cell_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_td:
            self.cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "td" and self.in_td:
            value = html.unescape(" ".join(self.cell_parts))
            self.row.append(re.sub(r"\s+", " ", value).strip())
            self.in_td = False
        elif tag == "tr":
            if self.row:
                self.rows.append(self.row)
            self.row = []


def now_ist() -> datetime:
    return datetime.now(IST)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, path)


def http_get(url: str, headers: dict[str, str] | None = None, timeout: int = 30) -> bytes:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json,text/html,*/*"}
    request_headers.update(headers or {})
    request = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def clean_number(value: Any) -> int | None:
    try:
        number = float(str(value).replace(",", "").strip())
        return round(number) if number >= 0 else None
    except (TypeError, ValueError):
        return None


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def format_record(raw: dict[str, Any]) -> dict[str, Any] | None:
    state = str(raw.get("state") or raw.get("State") or "").strip()
    district = str(raw.get("district") or raw.get("District") or "").strip()
    market = str(raw.get("market") or raw.get("Market") or raw.get("mandi") or "").strip()
    commodity = str(raw.get("commodity") or raw.get("Commodity") or "").strip()
    variety = str(raw.get("variety") or raw.get("Variety") or "FAQ").strip()
    grade = str(raw.get("grade") or raw.get("Grade") or "FAQ").strip()
    minimum = clean_number(raw.get("min_price") or raw.get("Min_Price"))
    maximum = clean_number(raw.get("max_price") or raw.get("Max_Price"))
    modal = clean_number(raw.get("modal_price") or raw.get("Modal_Price"))
    arrival_date = str(
        raw.get("arrival_date") or raw.get("Arrival_Date") or raw.get("price_date") or ""
    ).strip()
    if not all((state, district, market, commodity)) or modal in (None, 0):
        return None

    district_hi = DISTRICT_HI.get(district, district)
    commodity_hi = COMMODITY_HI.get(commodity, commodity)
    return {
        "state": state,
        "district": district,
        "district_hi": district_hi,
        "mandi": market,
        "mandi_hi": market if market.endswith("मंडी") else f"{market} मंडी",
        "commodity": commodity,
        "commodity_hi": commodity_hi,
        "variety": variety,
        "variety_hi": variety,
        "grade": grade,
        "grade_hi": grade,
        # The OGD price resource does not publish arrivals. Never invent one.
        "arrivals": None,
        "arrivals_unit": None,
        "arrivals_unit_hi": None,
        "min_price": minimum or modal,
        "max_price": maximum or modal,
        "modal_price": modal,
        "price_unit": "Quintal",
        "arrival_date": arrival_date,
        "source": "data.gov.in / AGMARKNET",
        "verified": True,
    }


def fetch_data_gov(api_key: str, state: str | None = None, max_records: int = 25000) -> list[dict[str, Any]]:
    if not api_key:
        return []

    output: list[dict[str, Any]] = []
    offset = 0
    page_size = 1000
    while offset < max_records:
        params: dict[str, Any] = {
            "api-key": api_key,
            "format": "json",
            "limit": min(page_size, max_records - offset),
            "offset": offset,
        }
        if state:
            params["filters[state]"] = state
        url = f"{DATA_GOV_API}?{urllib.parse.urlencode(params)}"
        payload = json.loads(http_get(url).decode("utf-8"))
        if payload.get("error"):
            raise RuntimeError(f"data.gov.in: {payload['error']}")
        page = payload.get("records") or []
        for raw in page:
            record = format_record(raw)
            if record:
                output.append(record)
        if len(page) < page_size:
            break
        offset += len(page)
    return output


def fetch_authorised_price_feed(url: str, api_key: str, source_name: str) -> list[dict[str, Any]]:
    """Read an approved government JSON feed without scraping a login page."""
    if not url:
        return []
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    payload = json.loads(http_get(url, headers=headers, timeout=35).decode("utf-8"))
    raw_records = payload.get("records") or payload.get("data") or payload.get("prices") or []
    records: list[dict[str, Any]] = []
    for raw in raw_records:
        record = format_record(raw)
        if record:
            record["source"] = source_name
            records.append(record)
    return records


def record_verification_key(record: dict[str, Any]) -> tuple[str, ...]:
    return tuple(normalize_name(str(record.get(field) or "")) for field in (
        "state", "district", "mandi", "commodity", "arrival_date"
    ))


def add_cross_verification(
    primary_records: list[dict[str, Any]],
    primary_source: str,
    secondary_feeds: list[tuple[str, list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    indexes = [
        (source, {record_verification_key(record): record for record in records})
        for source, records in secondary_feeds if records
    ]
    for record in primary_records:
        sources = [primary_source]
        key = record_verification_key(record)
        for source, index in indexes:
            other = index.get(key)
            if other and other.get("modal_price") == record.get("modal_price"):
                sources.append(source)
        record["verification_sources"] = sources
        record["verification_count"] = len(sources)
        record["cross_verified"] = len(sources) >= 2
        record["three_source_verified"] = len(sources) >= 3
    return primary_records


def fetch_agmarknet_up() -> list[dict[str, Any]]:
    page = http_get(AGMARKNET_URL, headers={"Accept": "text/html"}, timeout=35).decode(
        "utf-8", errors="ignore"
    )
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.DOTALL | re.IGNORECASE)
    output: list[dict[str, Any]] = []
    for row in rows:
        cells = [
            html.unescape(re.sub(r"<[^>]+>", " ", cell)).strip()
            for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
        ]
        cells = [re.sub(r"\s+", " ", cell) for cell in cells]
        if len(cells) < 11 or cells[1].casefold() != "uttar pradesh":
            continue
        record = format_record(
            {
                "state": cells[1], "district": cells[2], "market": cells[3],
                "commodity": cells[4], "variety": cells[5], "grade": cells[6],
                "min_price": cells[7], "max_price": cells[8], "modal_price": cells[9],
                "arrival_date": cells[10],
            }
        )
        if record:
            record["source"] = "AGMARKNET"
            output.append(record)
    return output


def fetch_mandi_contacts() -> tuple[list[dict[str, str]], str | None]:
    errors: list[str] = []
    for url in EMANDI_CONTACT_URLS:
        try:
            parser = ContactTableParser()
            parser.feed(http_get(url, headers={"Accept": "text/html"}, timeout=35).decode(
                "utf-8", errors="ignore"
            ))
            contacts: list[dict[str, str]] = []
            for row in parser.rows:
                if len(row) < 5 or not row[0].strip().isdigit():
                    continue
                mandi, name, designation, phone = (item.strip() for item in row[1:5])
                if mandi and phone:
                    contacts.append({
                        "mandi": mandi,
                        "name": name,
                        "designation": designation,
                        "phone": re.sub(r"[^0-9+]", "", phone),
                    })
            if contacts:
                return contacts, url
        except Exception as exc:  # upstream availability is recorded for diagnostics
            errors.append(f"{url}: {exc}")
    if errors:
        print("Contact feed unavailable:", " | ".join(errors))
    return [], None


def fetch_auction_feed() -> tuple[dict[str, Any], str]:
    feed_url = os.environ.get("ENAM_AUCTION_FEED_URL", "").strip()
    if not feed_url:
        return {
            "status": "configuration_required",
            "message_hi": "लाइव लॉट देखने के लिए अधिकृत e-NAM feed की आवश्यकता है। कोई नकली लॉट नहीं दिखाया गया है।",
            "message_en": "An authorised e-NAM feed is required for live lots. No simulated lots are shown.",
            "updated_at": None,
            "portal_url": ENAM_PORTAL_URL,
            "trade_url": ENAM_TRADE_URL,
            "lots": [],
        }, "not_configured"

    headers: dict[str, str] = {}
    api_key = os.environ.get("ENAM_AUCTION_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = json.loads(http_get(feed_url, headers=headers, timeout=35).decode("utf-8"))
    raw_lots = payload.get("lots") or payload.get("records") or payload.get("data") or []
    lots: list[dict[str, Any]] = []
    for raw in raw_lots:
        lot_number = str(raw.get("lot_number") or raw.get("lotId") or raw.get("lot_id") or "").strip()
        district = str(raw.get("district") or "").strip()
        mandi = str(raw.get("mandi") or raw.get("market") or raw.get("apmc") or "").strip()
        commodity = str(raw.get("commodity") or raw.get("crop_name") or "").strip()
        if not all((lot_number, district, mandi, commodity)):
            continue
        lots.append({
            "lot_number": lot_number,
            "state": str(raw.get("state") or "Uttar Pradesh"),
            "district": district,
            "mandi": mandi,
            "commodity": commodity,
            "variety": str(raw.get("variety") or ""),
            "grade": str(raw.get("grade") or ""),
            "quantity": clean_number(raw.get("quantity")),
            "quantity_unit": str(raw.get("quantity_unit") or raw.get("unit") or "Quintal"),
            "base_price": clean_number(raw.get("base_price") or raw.get("starting_rate")),
            "current_bid": clean_number(raw.get("current_bid") or raw.get("highest_bid")),
            "bid_count": clean_number(raw.get("bid_count")),
            "status": str(raw.get("status") or "active"),
            "starts_at": raw.get("starts_at"),
            "ends_at": raw.get("ends_at"),
            "assaying_certificate": raw.get("assaying_certificate"),
            "source_url": raw.get("source_url") or ENAM_PORTAL_URL,
        })
    return {
        "status": "live" if lots else "no_active_lots",
        "message_hi": "अधिकृत feed से प्राप्त जिला एवं लॉट-वार नीलामी।",
        "message_en": "District and lot-wise auction data from the authorised feed.",
        "updated_at": payload.get("updated_at") or now_ist().isoformat(),
        "portal_url": ENAM_PORTAL_URL,
        "trade_url": ENAM_TRADE_URL,
        "lots": lots,
    }, "ok"


def aggregate_state_prices(records: list[dict[str, Any]], source: str, verified: bool) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record.get("state") and record.get("modal_price"):
            grouped[record["state"]].append(record)

    states: list[dict[str, Any]] = []
    for state, rows in grouped.items():
        modal_values = [row["modal_price"] for row in rows if row.get("modal_price")]
        commodity_counts = Counter(row["commodity"] for row in rows if row.get("commodity"))
        top_markets = sorted(rows, key=lambda row: row.get("modal_price") or 0, reverse=True)[:8]
        states.append({
            "state": state,
            "district_count": len({row["district"] for row in rows}),
            "mandi_count": len({row["mandi"] for row in rows}),
            "record_count": len(rows),
            "average_modal_price": round(sum(modal_values) / len(modal_values)) if modal_values else None,
            "minimum_price": min((row["min_price"] for row in rows if row.get("min_price")), default=None),
            "maximum_price": max((row["max_price"] for row in rows if row.get("max_price")), default=None),
            "top_commodity": commodity_counts.most_common(1)[0][0] if commodity_counts else None,
            "markets": [
                {
                    "district": row["district"], "mandi": row["mandi"],
                    "commodity": row["commodity"], "modal_price": row["modal_price"],
                    "arrival_date": row.get("arrival_date"),
                }
                for row in top_markets
            ],
        })
    states.sort(key=lambda item: item["state"])
    return {
        "updated_at": now_ist().isoformat(),
        "source": source,
        "verified": verified,
        "states": states,
    }


def build_mandi_directory(
    records: list[dict[str, Any]], contacts: list[dict[str, str]], contact_source: str | None
) -> dict[str, Any]:
    contact_map: dict[str, list[dict[str, str]]] = defaultdict(list)
    for contact in contacts:
        contact_map[normalize_name(contact["mandi"])].append(contact)

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record.get("state") == "Uttar Pradesh":
            grouped[(record["district"], record["mandi"], record.get("mandi_hi") or record["mandi"])].append(record)

    mandis: list[dict[str, Any]] = []
    matched_contact_keys: set[str] = set()
    for (district, mandi, mandi_hi), rows in grouped.items():
        key = normalize_name(mandi.replace("APMC", "").replace("Mandi", ""))
        local_contacts = contact_map.get(key, [])
        if local_contacts:
            matched_contact_keys.add(key)
        if not local_contacts:
            # A conservative contains match handles names such as "Fatehpur APMC".
            matched_pair = next(
                ((name, value) for name, value in contact_map.items() if len(key) >= 5 and (key in name or name in key)),
                None,
            )
            if matched_pair:
                matched_contact_keys.add(matched_pair[0])
                local_contacts = matched_pair[1]
        prices = [row["modal_price"] for row in rows if row.get("modal_price")]
        mandis.append({
            "state": "Uttar Pradesh",
            "district": district,
            "district_hi": DISTRICT_HI.get(district, district),
            "mandi": mandi,
            "mandi_hi": mandi_hi,
            "address": None,
            "contacts": local_contacts,
            "central_helpdesk": ["+91-8765957686", "+91-8765958630"],
            "commodities": sorted({row["commodity"] for row in rows}),
            "commodity_count": len({row["commodity"] for row in rows}),
            "latest_price_date": max((row.get("arrival_date") or "" for row in rows), default=""),
            "minimum_modal_price": min(prices) if prices else None,
            "maximum_modal_price": max(prices) if prices else None,
            "official_contact_url": "https://emandi.up.gov.in/MandiHome/Contactus",
            "enam_portal_url": ENAM_PORTAL_URL,
            "map_url": "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote_plus(
                f"{mandi}, {district}, Uttar Pradesh"
            ),
        })

    # Keep official contact-only mandis visible even when they did not report a
    # price in the current AGMARKNET snapshot. The contact portal does not
    # publish a district/address for these rows, so those fields stay explicit.
    for contact_key, local_contacts in contact_map.items():
        if contact_key in matched_contact_keys:
            continue
        mandi_name = local_contacts[0]["mandi"]
        mandis.append({
            "state": "Uttar Pradesh",
            "district": "Not published",
            "district_hi": "प्रकाशित नहीं",
            "mandi": mandi_name,
            "mandi_hi": mandi_name,
            "address": None,
            "contacts": local_contacts,
            "central_helpdesk": ["+91-8765957686", "+91-8765958630"],
            "commodities": [],
            "commodity_count": 0,
            "latest_price_date": None,
            "minimum_modal_price": None,
            "maximum_modal_price": None,
            "official_contact_url": "https://emandi.up.gov.in/MandiHome/Contactus",
            "enam_portal_url": ENAM_PORTAL_URL,
            "map_url": "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote_plus(
                f"{mandi_name} Mandi, Uttar Pradesh"
            ),
        })
    mandis.sort(key=lambda item: (item["district"], item["mandi"]))
    return {
        "updated_at": now_ist().isoformat(),
        "source": contact_source or "AGMARKNET market list; e-Mandi contact portal unavailable",
        "central_office": {
            "name": "राज्य कृषि उत्पादन मण्डी परिषद्, उत्तर प्रदेश",
            "address": "किसान मंडी भवन, विभूति खंड, गोमती नगर, लखनऊ - 226010",
            "phones": ["+91-8765957686", "+91-8765958630"],
            "website": "https://emandi.up.gov.in/",
        },
        "mandis": mandis,
    }


def update_history(records: list[dict[str, Any]], reset: bool) -> dict[str, list[dict[str, Any]]]:
    history = {} if reset else read_json(DATA_DIR / "history.json", {})
    if not isinstance(history, dict):
        history = {}
    date_key = now_ist().date().isoformat()
    grouped: dict[str, list[int]] = defaultdict(list)
    for row in records:
        if row.get("commodity") and row.get("modal_price"):
            grouped[row["commodity"]].append(row["modal_price"])
    for commodity, values in grouped.items():
        points = history.get(commodity, [])
        points = [point for point in points if point.get("date") != date_key]
        points.append({"date": date_key, "price": round(sum(values) / len(values))})
        history[commodity] = points[-30:]
    return history


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    checked_at = now_ist().isoformat()
    api_key = os.environ.get("DATA_GOV_IN_API_KEY", "").strip()
    offline = os.environ.get("SKIP_EXTERNAL_FETCH", "").strip() == "1"
    previous = read_json(DATA_DIR / "latest.json", {})
    previous_records = previous.get("records", []) if isinstance(previous, dict) else []
    previous_verified = bool(previous.get("verified")) if isinstance(previous, dict) else False
    sources: list[dict[str, Any]] = []

    up_records: list[dict[str, Any]] = []
    all_india_records: list[dict[str, Any]] = []
    source_name = ""
    candidate_feeds: list[tuple[str, list[dict[str, Any]]]] = []

    # Source 1: official OGD API generated from AGMARKNET.
    try:
        if not api_key:
            raise RuntimeError("DATA_GOV_IN_API_KEY is not configured")
        if offline:
            raise RuntimeError("external fetch skipped for offline run")
        data_gov_up = fetch_data_gov(api_key, state="Uttar Pradesh", max_records=12000)
        if not data_gov_up:
            raise RuntimeError("official API returned no Uttar Pradesh records")
        candidate_feeds.append(("data.gov.in", data_gov_up))
        sources.append({"name": "data.gov.in", "status": "ok", "records": len(data_gov_up)})
        try:
            all_india_records = fetch_data_gov(api_key, max_records=25000)
            sources.append({"name": "data.gov.in state feed", "status": "ok", "records": len(all_india_records)})
        except Exception as exc:
            sources.append({"name": "data.gov.in state feed", "status": "error", "message": str(exc)})
    except Exception as exc:
        sources.append({"name": "data.gov.in", "status": "error", "message": str(exc)})

    # Source 2: direct public AGMARKNET table, checked independently for a
    # matching modal price rather than used only as an invisible fallback.
    if not offline:
        try:
            agmarknet_up = fetch_agmarknet_up()
            if not agmarknet_up:
                raise RuntimeError("AGMARKNET returned no parseable records")
            candidate_feeds.append(("AGMARKNET", agmarknet_up))
            sources.append({"name": "AGMARKNET", "status": "ok", "records": len(agmarknet_up)})
        except Exception as exc:
            sources.append({"name": "AGMARKNET", "status": "error", "message": str(exc)})
    else:
        sources.append({"name": "AGMARKNET", "status": "not_checked", "message": "offline repository refresh"})

    # Sources 3 and 4: optional approved JSON feeds. These adapters never use
    # portal usernames/passwords and clearly report when no authorised feed was
    # supplied by e-NAM or UP e-Mandi.
    authorised_price_sources = (
        ("e-NAM trade feed", "ENAM_TRADE_FEED_URL", "ENAM_TRADE_API_KEY"),
        ("UP e-Mandi trade feed", "UP_EMANDI_TRADE_FEED_URL", "UP_EMANDI_TRADE_API_KEY"),
    )
    for display_name, url_env, key_env in authorised_price_sources:
        feed_url = os.environ.get(url_env, "").strip()
        feed_key = os.environ.get(key_env, "").strip()
        if not feed_url:
            sources.append({"name": display_name, "status": "not_configured", "records": 0})
            continue
        if offline:
            sources.append({"name": display_name, "status": "not_checked", "records": 0})
            continue
        try:
            records = fetch_authorised_price_feed(feed_url, feed_key, display_name)
            if not records:
                raise RuntimeError("authorised feed returned no parseable price records")
            candidate_feeds.append((display_name, records))
            sources.append({"name": display_name, "status": "ok", "records": len(records)})
        except Exception as exc:
            sources.append({"name": display_name, "status": "error", "message": str(exc)})

    if candidate_feeds:
        source_name, primary_records = candidate_feeds[0]
        checked_records = add_cross_verification(primary_records, source_name, candidate_feeds[1:])
        # The public dashboard is intentionally stricter than a normal single-
        # source reader: publish a price only after three government feeds agree.
        up_records = [record for record in checked_records if record.get("three_source_verified")]
        if up_records:
            source_name = "3-source verified: " + ", ".join(name for name, records in candidate_feeds if records)
        sources.append({
            "name": "3-source verification gate",
            "status": "ok" if up_records else "insufficient_sources",
            "records": len(up_records),
            "message": f"{len(up_records)} of {len(checked_records)} records matched across 3+ feeds",
        })
    fresh_verified_data = bool(up_records)
    if not up_records:
        if previous_verified:
            up_records = previous_records
            source_name = previous.get("source", "Last verified snapshot") if isinstance(previous, dict) else ""
            print("No official price source was reachable; retaining the last verified snapshot.")
        else:
            up_records = []
            source_name = "Official feed unavailable"
            print("No verified snapshot exists; legacy generated rates were not retained.")

    # State summaries also use only records that passed the same 3-source gate.
    # A single all-India OGD response is monitored but never published alone.
    all_india_records = up_records

    contacts, contact_source = ([], None) if offline else fetch_mandi_contacts()
    sources.append({
        "name": "UP e-Mandi contacts",
        "status": "ok" if contacts else "unavailable",
        "records": len(contacts),
        "url": contact_source,
    })

    try:
        auction, auction_status = fetch_auction_feed()
        sources.append({"name": "e-NAM authorised auction feed", "status": auction_status, "records": len(auction["lots"])})
    except Exception as exc:
        auction = {
            "status": "temporarily_unavailable",
            "message_hi": "अधिकृत e-NAM feed अभी उपलब्ध नहीं है। कोई simulated lot नहीं दिखाया गया है।",
            "message_en": "The authorised e-NAM feed is unavailable. No simulated lots are shown.",
            "updated_at": None,
            "portal_url": ENAM_PORTAL_URL,
            "trade_url": ENAM_TRADE_URL,
            "lots": [],
        }
        sources.append({"name": "e-NAM authorised auction feed", "status": "error", "message": str(exc)})

    effective_verified = fresh_verified_data or previous_verified
    effective_updated_at = (
        checked_at if fresh_verified_data
        else previous.get("updated_at") if previous_verified
        else None
    )
    latest_payload = {
        "updated_at": effective_updated_at,
        "last_checked_at": checked_at,
        "source": source_name,
        "verified": effective_verified,
        "is_live": fresh_verified_data,
        "connected_price_sources": [name for name, records in candidate_feeds if records],
        "connected_price_source_count": len([1 for _, records in candidate_feeds if records]),
        "cross_verified_record_count": sum(1 for record in up_records if record.get("cross_verified")),
        "three_source_verified_record_count": sum(1 for record in up_records if record.get("three_source_verified")),
        "verification_note": (
            "A record is cross-verified only when another configured government feed reports the same market, commodity, date and modal price."
        ),
        "update_frequency": "6 times daily",
        "update_slots_ist": list(UPDATE_SLOTS_IST),
        "records": up_records,
    }

    state_prices = aggregate_state_prices(all_india_records, source_name, effective_verified)
    directory = build_mandi_directory(up_records, contacts, contact_source)
    # Discard legacy generated trend points until a verified source has built a
    # real history over successive refreshes.
    history = update_history(up_records, reset=not previous_verified)
    sources_payload = {
        "last_checked_at": checked_at,
        "update_frequency": "6 times daily",
        "update_slots_ist": list(UPDATE_SLOTS_IST),
        "sources": sources,
        "policy": "No simulated prices, arrivals, contacts, lots, or bids are generated.",
    }

    write_json_atomic(DATA_DIR / "latest.json", latest_payload)
    write_json_atomic(DATA_DIR / "history.json", history)
    write_json_atomic(DATA_DIR / "state_prices.json", state_prices)
    write_json_atomic(DATA_DIR / "mandis.json", directory)
    write_json_atomic(DATA_DIR / "auction.json", auction)
    write_json_atomic(DATA_DIR / "sources.json", sources_payload)
    print(
        f"Updated dashboard: {len(up_records)} UP prices, {len(state_prices['states'])} states, "
        f"{len(directory['mandis'])} mandis, {len(auction['lots'])} official auction lots."
    )


if __name__ == "__main__":
    main()
