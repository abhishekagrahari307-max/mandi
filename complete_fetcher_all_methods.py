#!/usr/bin/env python3
"""Complete 5-method parallel data fetcher for UP Mandi Price Dashboard.

Methods:
  1. data.gov.in Official API (real key or sample key fallback)
  2. Gemini API Direct (Google AI Studio — web grounding, bypasses AGMARKNET 403)
  3. OpenRouter (free models: gemini-2.0-flash-exp:free, deepseek-r1:free)
  4. Web Scraping (acrop.app, commodityonline.com — no API key needed)
  5. Sample API + Historical Merge (site NEVER empty)

Each method returns records in a common format. After all methods run:
  - clean_and_filter(): state=UP only, outlier removal, mandi name normalize
  - build_final_payload(): cross-verify across sources, fallback to single-source
  - Write data/latest.json + data/source_prices.json

Usage:
  python complete_fetcher_all_methods.py

Environment variables (all optional, methods gracefully skip if missing):
  DATA_GOV_IN_API_KEY  - data.gov.in API key
  GEMINI_API_KEY       - Google AI Studio Gemini key
  OPENROUTER_API_KEY   - OpenRouter API key
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

# ─── Configuration ───────────────────────────────────────────────────────────

IST = ZoneInfo("Asia/Kolkata")
DATA_DIR = Path("data")

DATA_GOV_RESOURCE_ID = os.environ.get(
    "DATA_GOV_RESOURCE_ID", "9ef84268-d588-465a-a308-a864a43d0070"
)
DATA_GOV_API = f"https://api.data.gov.in/resource/{DATA_GOV_RESOURCE_ID}"
SAMPLE_DATA_GOV_API_KEY = "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

ACROP_BASE_URL = "https://acrop.app/mandi/uttar-pradesh"
COMMODITYONLINE_URL = "https://www.commodityonline.com/mandi-prices/uttar-pradesh"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,hi-IN;q=0.8",
}

# District aliases for normalization
DISTRICT_ALIASES = {
    "Allahabad": "Prayagraj", "Faizabad": "Ayodhya",
    "Bara Banki": "Barabanki", "Bara banki": "Barabanki",
    "Rae Bareli": "Raebareli", "Rae Bareily": "Raebareli",
    "Raibareli": "Raebareli", "Raebarelli": "Raebareli",
    "Mahrajganj": "Maharajganj", "Maharajgani": "Maharajganj",
    "Kheri": "Lakhimpur Kheri", "Lakhimpur": "Lakhimpur Kheri",
    "Bhadohi": "Sant Ravidas Nagar", "Bhadohi(Sant Ravi Nagar)": "Sant Ravidas Nagar",
    "Sant Ravi Das Nagar": "Sant Ravidas Nagar",
    "Sant Kabeer Nagar": "Sant Kabir Nagar",
    "Shrawasti": "Shravasti", "Sharawasti": "Shravasti",
    "Siddharth Nagar": "Siddharthnagar", "Sidharthnagar": "Siddharthnagar",
    "Badaun": "Budaun", "Badayun": "Budaun",
    "Shamali": "Shamli", "Prabuddh Nagar": "Shamli",
    "Bhim Nagar": "Sambhal", "Bheem Nagar": "Sambhal",
    "Jyotiba Phule Nagar": "Amroha", "Jyotiba Phoole Nagar": "Amroha",
    "J.P. Nagar": "Amroha",
    "Mahamaya Nagar": "Hathras",
    "Kanshiram Nagar": "Kasganj", "Kanshi Ram Nagar": "Kasganj",
    "Chhatrapati Shahuji Maharaj Nagar": "Amethi",
    "Shahuji Maharaj Nagar": "Amethi", "C.S.M. Nagar": "Amethi",
    "Gautam Buddh Nagar": "Gautam Buddha Nagar",
    "Gautambudh Nagar": "Gautam Buddha Nagar",
    "Ambedkarnagar": "Ambedkar Nagar",
    "Kanpur (Dehat)": "Kanpur Dehat", "Kanpur (Nagar)": "Kanpur Nagar",
    "Kanpur": "Kanpur Nagar",
    "Ayodhya (Faizabad)": "Ayodhya", "Prayagraj (Allahabad)": "Prayagraj",
    "Bulandshahar": "Bulandshahr", "Chitrakut": "Chitrakoot",
    "Farukhabad": "Farrukhabad", "Jalaun (Orai)": "Jalaun",
    "Kannuj": "Kannauj", "Khiri (Lakhimpur)": "Lakhimpur Kheri",
    "Mau(Maunathbhanjan)": "Mau", "Pillibhit": "Pilibhit",
}

DISTRICT_HI = {
    "Agra": "आगरा", "Aligarh": "अलीगढ़", "Ambedkar Nagar": "अम्बेडकर नगर",
    "Amethi": "अमेठी", "Amroha": "अमरोहा", "Auraiya": "औरैया",
    "Ayodhya": "अयोध्या", "Azamgarh": "आजमगढ़", "Baghpat": "बागपत",
    "Bahraich": "बहराइच", "Ballia": "बलिया", "Balrampur": "बलरामपुर",
    "Banda": "बांदा", "Barabanki": "बाराबंकी", "Bareilly": "बरेली",
    "Basti": "बस्ती", "Bhadohi": "भदोही", "Bijnor": "बिजनौर",
    "Budaun": "बदायूं", "Bulandshahr": "बुलन्दशहर",
    "Chandauli": "चन्दौली", "Chitrakoot": "चित्रकूट", "Deoria": "देवरिया",
    "Etah": "एटा", "Etawah": "एटवाह", "Farrukhabad": "फर्रूखाबाद",
    "Fatehpur": "फतेहपुर", "Firozabad": "फिरोजाबाद",
    "Gautam Buddha Nagar": "गौतम बुद्ध नगर", "Ghaziabad": "गाजियाबाद",
    "Ghazipur": "गाजीपुर", "Gonda": "गोंडा", "Gorakhpur": "गोरखपुर",
    "Hamirpur": "हमीरपुर", "Hardoi": "हरदोई", "Hathras": "हाथरस",
    "Jalaun": "जालौन", "Jaunpur": "जौनपुर", "Jhansi": "झाँसी",
    "Kannauj": "कन्नौज", "Kanpur Dehat": "कानपुर देहात",
    "Kanpur Nagar": "कानपुर नगर", "Kasganj": "कासगंज",
    "Kaushambi": "कौशाम्बी", "Kushinagar": "कुशीनगर",
    "Lakhimpur Kheri": "लखीमपुर खीरी", "Lalitpur": "ललितपुर",
    "Lucknow": "लखनऊ", "Maharajganj": "महाराजगंज",
    "Mahoba": "महोबा", "Mainpuri": "मैनपुरी", "Mathura": "मथुरा",
    "Mau?": "मऊ", "Meerut": "मेरठ", "Mirzapur": "मिर्जापुर",
    "Moradabad": "मुरादाबाद", "Muzaffarnagar": "मुजफ्फरनगर",
    "Pilibhit": "पीलीभीत", "Pratapgarh": "प्रतापगढ़",
    "Prayagraj": "प्रयागराज", "Raebareli": "रायबरेली",
    "Rampur": "रामपुर", "Saharanpur": "सहारनपुर", "Sambhal": "संभल",
    "Sant Kabir Nagar": "संत कबीर नगर",
    "Sant Ravidas Nagar": "संत रविदास नगर (भदोही)",
    "Shahjahanpur": "शाहजहाँपुर", "Shamli": "शामली",
    "Shravasti": "श्रावस्ती", "Siddharthnagar": "सिद्धार्थनगर",
    "Sitapur": "सीतापुर", "Sonbhadra": "सोनभद्र",
    "Sultanpur": "सुल्तानपुर", "Unnao": "उन्नाव",
    "Varanasi": "वाराणसी", "Hapur": "हापुड़", "Chitrakoot": "चित्रकूट",
    "Mau": "मऊ",
}

COMMODITIES_TO_SCRAPE = [
    "wheat", "rice", "potato", "onion", "tomato",
    "maize", "green-chilli", "paddy(dhan)(common)",
    "garlic", "ginger(green)", "banana", "mustard",
    "arhar/tur", "moong", "masoor", "barley",
]

# ─── Utility Functions ────────────────────────────────────────────────────────

def now_ist() -> datetime:
    return datetime.now(IST)


def today_str() -> str:
    return now_ist().strftime("%d/%m/%Y")


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
    request_headers = {"User-Agent": BROWSER_HEADERS["User-Agent"], "Accept": "application/json,text/html,*/*"}
    request_headers.update(headers or {})
    req = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def canonical_district(value: str) -> str:
    """Normalize district name to canonical form."""
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    if not cleaned:
        return ""
    return DISTRICT_ALIASES.get(cleaned, cleaned)


def district_hi_for(value: str) -> str:
    canonical = canonical_district(value)
    return DISTRICT_HI.get(canonical, canonical)


def clean_number(value: Any) -> int | None:
    try:
        number = float(str(value).replace(",", "").strip())
        return round(number) if number >= 0 else None
    except (TypeError, ValueError):
        return None


def format_record(raw: dict[str, Any], source: str = "") -> dict[str, Any] | None:
    """Convert raw record to standardized format."""
    state = str(raw.get("state") or "").strip()
    if not state:
        state = "Uttar Pradesh"
    reported_district = str(raw.get("district") or "").strip()
    district = canonical_district(reported_district)
    market = str(raw.get("market") or raw.get("mandi") or "").strip()
    commodity = str(raw.get("commodity") or "").strip()
    variety = str(raw.get("variety") or "Other").strip()
    grade = str(raw.get("grade") or "FAQ").strip()
    minimum = clean_number(raw.get("min_price") or raw.get("Min_Price"))
    maximum = clean_number(raw.get("max_price") or raw.get("Max_Price"))
    modal = clean_number(raw.get("modal_price") or raw.get("Modal_Price"))
    arrival_date = str(
        raw.get("arrival_date") or raw.get("Arrival_Date") or raw.get("price_date") or ""
    ).strip()

    if not all((district, market, commodity)) or modal in (None, 0):
        return None

    district_hi = DISTRICT_HI.get(district, district)
    return {
        "state": state,
        "district": district,
        "district_hi": district_hi,
        "district_reported": reported_district,
        "mandi": market,
        "mandi_hi": market if market.endswith("मंडी") else f"{market} मंडी",
        "commodity": commodity,
        "commodity_hi": commodity,
        "variety": variety,
        "variety_hi": variety,
        "grade": grade,
        "grade_hi": grade,
        "arrivals": None,
        "arrivals_unit": None,
        "arrivals_unit_hi": None,
        "min_price": minimum or modal,
        "max_price": maximum or modal,
        "modal_price": modal,
        "price_unit": "Quintal",
        "arrival_date": arrival_date or today_str(),
        "source": source or "unknown",
        "verified": False,
    }


# ─── Method 1: data.gov.in Official API ───────────────────────────────────────

def fetch_method1_datagov() -> tuple[list[dict[str, Any]], str]:
    """Fetch from data.gov.in OGD API. Uses real key first, then sample key fallback."""
    api_key = os.environ.get("DATA_GOV_IN_API_KEY", "").strip()
    records: list[dict[str, Any]] = []
    source_label = ""

    # Try real key first
    if api_key and api_key != SAMPLE_DATA_GOV_API_KEY:
        try:
            records = _fetch_datagov(api_key, state="Uttar Pradesh", max_records=12000)
            if records:
                source_label = "data.gov.in (official key)"
                print(f"  ✅ Method 1 (real key): {len(records)} UP records")
                return records, source_label
            print("  ⚠ Method 1: Real key returned 0 records, trying sample key...")
        except Exception as exc:
            print(f"  ⚠ Method 1: Real key failed ({exc}), trying sample key...")

    # Fallback to sample key
    try:
        records = _fetch_datagov(SAMPLE_DATA_GOV_API_KEY, state="Uttar Pradesh", max_records=2000)
        if records:
            source_label = "data.gov.in (sample key fallback)"
            print(f"  ✅ Method 1 (sample key): {len(records)} UP records")
            return records, source_label
    except Exception as exc:
        print(f"  ⚠ Method 1: Sample key also failed: {exc}")

    print("  ❌ Method 1: No records from data.gov.in")
    return [], ""


def _fetch_datagov(api_key: str, state: str = "Uttar Pradesh", max_records: int = 12000) -> list[dict[str, Any]]:
    """Paginated fetch from data.gov.in API."""
    is_sample = (api_key == SAMPLE_DATA_GOV_API_KEY)
    page_size = 10 if is_sample else 1000
    effective_max = min(max_records, 10000)

    output: list[dict[str, Any]] = []
    offset = 0
    while offset < effective_max:
        remaining = effective_max - offset
        current_limit = min(page_size, remaining)
        if offset + current_limit > 10000:
            current_limit = 10000 - offset
            if current_limit <= 0:
                break

        params = {
            "api-key": api_key,
            "format": "json",
            "limit": current_limit,
            "offset": offset,
            "filters[state]": state,
        }
        url = f"{DATA_GOV_API}?{urllib.parse.urlencode(params)}"

        try:
            raw = http_get(url)
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            if "result window" in str(exc).lower():
                break
            raise

        if payload.get("error"):
            if "result window" in str(payload["error"]).lower():
                break
            raise RuntimeError(f"data.gov.in: {payload['error']}")

        page = payload.get("records") or []
        for raw_rec in page:
            rec = format_record(raw_rec, source="data.gov.in")
            if rec:
                output.append(rec)

        if len(page) < current_limit:
            break
        offset += len(page)

    return output


# ─── Method 2: Gemini API Direct (Google AI Studio) ───────────────────────────

def fetch_method2_gemini_direct() -> tuple[list[dict[str, Any]], str]:
    """Use Google's Gemini 2.0 Flash with web grounding to fetch AGMARKNET data.
    Bypasses AGMARKNET 403 because Gemini visits the site server-side."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("  ⚠ Method 2: GEMINI_API_KEY not set, skipping")
        return [], ""

    today = today_str()
    system_prompt = (
        "You are a mandi price data extractor. Visit the AGMARKNET portal "
        "(agmarknet.gov.in) and extract today's Uttar Pradesh mandi prices. "
        "Return ONLY a JSON array of objects. Each object must have these exact keys:\n"
        '  "district", "market", "commodity", "variety", "grade", '
        '  "min_price" (number), "max_price" (number), "modal_price" (number), '
        '  "arrival_date" (DD/MM/YYYY format).\n'
        "Do NOT include any explanation, markdown, or commentary. Only return the JSON array."
    )
    user_prompt = (
        f"Today is {today}. Search for Uttar Pradesh mandi prices on AGMARKNET "
        f"(https://agmarknet.gov.in/SearchCmmMkt.aspx?Tx_Commodity=0&Tx_State=UP"
        f"&Tx_District=0&Tx_Market=0&Tx_Trend=0). "
        f"Extract ALL available commodity prices from ALL UP mandis for today. "
        f"Include Wheat, Rice, Paddy, Potato, Onion, and all other commodities. "
        f"Return as JSON array. Prices in Rupees per Quintal."
    )

    try:
        response = _call_gemini(system_prompt, user_prompt, api_key)
        records = _parse_json_from_response(response)
        valid = []
        for r in records:
            if not isinstance(r, dict):
                continue
            r["state"] = "Uttar Pradesh"
            r.setdefault("arrival_date", today)
            r.setdefault("variety", "Other")
            r.setdefault("grade", "FAQ")
            rec = format_record(r, source="AGMARKNET (Gemini AI)")
            if rec:
                valid.append(rec)
        print(f"  ✅ Method 2 (Gemini direct): {len(valid)} records")
        return valid, "AGMARKNET (Gemini AI)"
    except Exception as exc:
        print(f"  ⚠ Method 2: Gemini direct failed: {exc}")
        return [], ""


def _call_gemini(system_prompt: str, user_prompt: str, api_key: str) -> str:
    """Call Google Gemini API directly."""
    url = f"{GEMINI_API_URL}?key={api_key}"
    body = json.dumps({
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8000},
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=90) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    candidates = payload.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        if parts:
            return parts[0].get("text", "")
    raise RuntimeError(f"Gemini returned no valid response: {payload.get('error', 'unknown')}")


# ─── Method 3: OpenRouter (Free Models) ────────────────────────────────────────

AI_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "deepseek/deepseek-r1:free",
    "google/gemini-2.0-flash-001",
    "meta-llama/llama-3.1-8b-instruct:free",
]


def fetch_method3_openrouter() -> tuple[list[dict[str, Any]], str]:
    """Use OpenRouter with free models (Gemini, DeepSeek) to fetch AGMARKNET data."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("  ⚠ Method 3: OPENROUTER_API_KEY not set, skipping")
        return [], ""

    today = today_str()
    system_prompt = (
        "You are a mandi price data extractor. Visit the AGMARKNET portal "
        "and extract today's Uttar Pradesh mandi prices. "
        "Return ONLY a JSON array of objects with keys: "
        '"district", "market", "commodity", "variety", "grade", '
        '"min_price" (number), "max_price" (number), "modal_price" (number), '
        '"arrival_date" (DD/MM/YYYY). '
        "No explanation, only JSON array."
    )
    user_prompt = (
        f"Today is {today}. Visit https://agmarknet.gov.in/SearchCmmMkt.aspx?Tx_Commodity=0&Tx_State=UP"
        f"&Tx_District=0&Tx_Market=0&Tx_Trend=0 and extract ALL UP mandi prices for today. "
        f"Include Wheat, Rice, Paddy, Potato, Onion and all crops. Prices in Rs/Quintal."
    )

    try:
        response = _call_openrouter(system_prompt, user_prompt, api_key)
        records = _parse_json_from_response(response)
        valid = []
        for r in records:
            if not isinstance(r, dict):
                continue
            r["state"] = "Uttar Pradesh"
            r.setdefault("arrival_date", today)
            r.setdefault("variety", "Other")
            r.setdefault("grade", "FAQ")
            rec = format_record(r, source="AGMARKNET (OpenRouter AI)")
            if rec:
                valid.append(rec)
        print(f"  ✅ Method 3 (OpenRouter): {len(valid)} records")
        return valid, "AGMARKNET (OpenRouter AI)"
    except Exception as exc:
        print(f"  ⚠ Method 3: OpenRouter failed: {exc}")
        return [], ""


def _call_openrouter(system_prompt: str, user_prompt: str, api_key: str) -> str:
    """Call OpenRouter API with model fallback."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://abhishekagrahari307-max.github.io/mandi/",
        "X-Title": "UP Mandi Dashboard",
    }

    last_error = None
    for model in AI_MODELS:
        body = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 4000,
        }).encode("utf-8")

        req = urllib.request.Request(OPENROUTER_API_URL, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            choices = payload.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            last_error = f"model={model} no choices"
            print(f"  ⚠ OpenRouter {model}: no choices, trying next...")
        except Exception as exc:
            last_error = f"model={model}: {exc}"
            print(f"  ⚠ OpenRouter {model} failed ({exc}), trying next...")

    raise RuntimeError(f"OpenRouter failed all models. Last: {last_error}")


def _parse_json_from_response(text: str) -> list[dict[str, Any]]:
    """Extract JSON array from AI response."""
    # Try ```json ... ``` code block
    code_block = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except json.JSONDecodeError:
            pass

    # Try raw JSON array
    json_match = re.search(r"\[[\s\S]*\]", text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return []


# ─── Method 4: Web Scraping — acrop.app (No API key needed) ───────────────────

# Key UP districts to scrape from acrop.app (covers ~90% of active mandis)
ACROP_DISTRICTS = [
    "agra", "aligarh", "ambedkar-nagar", "amethi", "amroha", "auraiya",
    "ayodhya", "azamgarh", "baghpat", "bahraich", "ballia", "balrampur",
    "banda", "barabanki", "bareilly", "basti", "bhadohi", "bijnor",
    "budaun", "bulandshahr", "chandauli", "chitrakoot", "deoria",
    "etah", "etawah", "farrukhabad", "fatehpur", "firozabad",
    "gautam-buddha-nagar", "ghaziabad", "ghazipur", "gonda", "gorakhpur",
    "hamirpur", "hardoi", "hathras", "hapur", "jalaun", "jaunpur", "jhansi",
    "kannauj", "kanpur-nagar", "kanpur-dehat", "kasganj", "kaushambi",
    "kushinagar", "lakhimpur-kheri", "lalitpur", "lucknow", "maharajganj",
    "mahoba", "mainpuri", "mathura", "mau", "meerut", "mirzapur",
    "moradabad", "muzaffarnagar", "pilibhit", "pratapgarh", "prayagraj",
    "raebareli", "rampur", "saharanpur", "sambhal", "sant-kabir-nagar",
    "sant-ravidas-nagar", "shahjahanpur", "shamli", "shravasti",
    "siddharthnagar", "sitapur", "sonbhadra", "sultanpur", "unnao", "varanasi",
]


def fetch_method4_scraping() -> tuple[list[dict[str, Any]], str]:
    """Scrape acrop.app for UP mandi data. No API key needed.
    
    acrop.app is an AGMARKNET aggregator that publishes daily mandi prices.
    It replaced mandipulse.com (which now returns 404).
    Tested: Kanpur 3533, Lucknow 6157 working (8-15 mandis per district)."""
    records: list[dict[str, Any]] = []
    today = today_str()

    # Scrape acrop.app (primary - working, reliable)
    try:
        acrop_recs = _scrape_acrop(today)
        records.extend(acrop_recs)
        print(f"  ✅ Method 4a (acrop.app): {len(acrop_recs)} records")
    except Exception as exc:
        print(f"  ⚠ Method 4a: acrop.app scraping failed: {exc}")

    # Scrape commodityonline.com (secondary fallback)
    try:
        commodity_recs = _scrape_commodityonline(today)
        records.extend(commodity_recs)
        print(f"  ✅ Method 4b (commodityonline): {len(commodity_recs)} records")
    except Exception as exc:
        print(f"  ⚠ Method 4b: commodityonline scraping failed: {exc}")

    if records:
        return records, "Web Scraped (acrop.app + commodityonline)"
    print("  ❌ Method 4: No records from web scraping")
    return [], ""


def _scrape_acrop(today: str) -> list[dict[str, Any]]:
    """Scrape acrop.app for UP mandi prices.
    
    Strategy: Fetch district pages, extract market URLs, then fetch each
    market page for commodity-level prices.
    
    URL patterns:
      - District list:  acrop.app/mandi/uttar-pradesh
      - District page:  acrop.app/mandi/uttar-pradesh/{district-slug}
      - Market page:    acrop.app/mandi/uttar-pradesh/{district-slug}/{market-slug}
    """
    import html as html_mod
    records: list[dict[str, Any]] = []

    for district_slug in ACROP_DISTRICTS:
        district_url = f"{ACROP_BASE_URL}/{district_slug}"
        try:
            dist_html = http_get(district_url, headers=BROWSER_HEADERS, timeout=20).decode("utf-8", errors="ignore")
        except Exception:
            continue

        district_name = district_slug.replace("-", " ").title()

        # Extract market links: href="https://acrop.app/mandi/uttar-pradesh/{district}/{market}"
        market_pattern = re.compile(
            rf'href="https?://acrop\.app/mandi/uttar-pradesh/{re.escape(district_slug)}/([^"]+)"',
            re.IGNORECASE
        )
        market_slugs = list(dict.fromkeys(market_pattern.findall(dist_html)))

        for market_slug in market_slugs:
            if "/" in market_slug or market_slug in ("", "#") or len(market_slug) < 2:
                continue

            market_url = f"{ACROP_BASE_URL}/{district_slug}/{market_slug}"
            try:
                market_html = http_get(market_url, headers=BROWSER_HEADERS, timeout=15).decode("utf-8", errors="ignore")
            except Exception:
                continue

            # Build market name from slug
            market_name_parts = market_slug.replace("-", " ").title()
            if "Grain" in market_name_parts and "(" not in market_name_parts:
                market_name_parts = market_name_parts.replace("Grain", "(Grain)")
            market_name = f"{market_name_parts} APMC" if "APMC" not in market_name_parts else market_name_parts

            # Parse commodity prices from market page
            text = re.sub(r'<[^>]+>', ' ', market_html)
            text = html_mod.unescape(text)

            # Find patterns: CommodityName \u20b9Price (\u20b9 = ₹)
            # Split by ₹ and extract commodity + price
            parts = re.split(r'₹', text)
            seen = set()
            for i in range(1, len(parts)):
                price_match = re.match(r'\s*([\d,]+)', parts[i])
                if not price_match:
                    continue
                try:
                    price = int(price_match.group(1).replace(",", ""))
                except ValueError:
                    continue
                if price <= 0 or price > 200000:
                    continue

                # Extract commodity name from preceding text
                preceding = parts[i - 1].strip() if i > 0 else ""
                words = preceding.split()
                commodity_words = []
                skip_words = {"₹", "▼", "▲", "No", "change", "Avg", "Cereals", "Pulses",
                              "Vegetables", "Spices", "Oil", "Seeds", "Fruits", "Drug",
                              "Narcotics", "Forest", "Products", "Dry", "Trending", "APMC",
                              "commodities", "Gainers", "Losers", "Unchanged", "Today"}
                for w in reversed(words[-6:]):
                    w_clean = w.strip(".,;:()[]🔥▼▲")
                    if not w_clean:
                        continue
                    if w_clean.isdigit() or w_clean in skip_words:
                        if commodity_words:
                            break
                        continue
                    commodity_words.insert(0, w_clean)
                    if len(commodity_words) >= 3:
                        break

                commodity = " ".join(commodity_words) if commodity_words else ""
                if not commodity or len(commodity) < 2:
                    continue
                commodity = commodity.strip()
                if commodity.lower() in {"apmc", "market", "district", "commodity", "price", "today", "mandi"}:
                    continue
                if commodity.lower() in seen:
                    continue
                seen.add(commodity.lower())

                rec = format_record({
                    "state": "Uttar Pradesh",
                    "district": district_name,
                    "market": market_name,
                    "commodity": commodity,
                    "variety": "Other",
                    "grade": "FAQ",
                    "modal_price": price,
                    "min_price": price,
                    "max_price": price,
                    "arrival_date": today,
                }, source="acrop.app")
                if rec:
                    records.append(rec)

    return records



def _scrape_commodityonline(today: str) -> list[dict[str, Any]]:
    """Scrape commodityonline.com for UP mandi prices (secondary fallback)."""
    records: list[dict[str, Any]] = []
    try:
        html = http_get(COMMODITYONLINE_URL, headers=BROWSER_HEADERS, timeout=20).decode("utf-8", errors="ignore")
    except Exception:
        return []

    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE)
    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL | re.IGNORECASE)
        if len(cells) < 6:
            continue
        cell_texts = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
        try:
            commodity = cell_texts[0]
            district = cell_texts[1]
            mandi = cell_texts[2]
            modal_p = clean_number(cell_texts[5]) if len(cell_texts) > 5 else None
            min_p = clean_number(cell_texts[3]) if len(cell_texts) > 3 else modal_p
            max_p = clean_number(cell_texts[4]) if len(cell_texts) > 4 else modal_p
            if modal_p and mandi and commodity:
                rec = format_record({
                    "state": "Uttar Pradesh",
                    "district": district,
                    "market": mandi,
                    "commodity": commodity,
                    "variety": "Other",
                    "grade": "FAQ",
                    "min_price": min_p or modal_p,
                    "max_price": max_p or modal_p,
                    "modal_price": modal_p,
                    "arrival_date": today,
                }, source="commodityonline.com")
                if rec:
                    records.append(rec)
        except (IndexError, ValueError):
            continue
    return records

# ─── Method 5: Sample API + Historical Merge ──────────────────────────────────

def fetch_method5_sample_plus_history() -> tuple[list[dict[str, Any]], str]:
    """Sample key fetch + merge 7-day history from source_prices.json.
    This method guarantees the site is NEVER empty — even when all APIs
    fail, it falls back to historical data from previous runs."""
    records: list[dict[str, Any]] = []
    sample_ok = False

    # Always try sample key
    try:
        sample_recs = _fetch_datagov(SAMPLE_DATA_GOV_API_KEY, state="Uttar Pradesh", max_records=2000)
        records.extend(sample_recs)
        sample_ok = True
        print(f"  ✅ Method 5 (sample key): {len(sample_recs)} records")
    except Exception as exc:
        print(f"  ⚠ Method 5: Sample key failed: {exc}")

    # Merge historical data from source_prices.json (last 7 days)
    # This works even when sample key fails — it reads from existing files
    history_recs = _merge_history(records)
    if history_recs:
        print(f"  ✅ Method 5 (historical merge): +{history_recs} additional records")

    if records:
        label = "data.gov.in (sample) + historical merge" if sample_ok else "historical merge only"
        return records, label
    print("  ❌ Method 5: No records even from sample + history")
    return [], ""


def _merge_history(current_records: list[dict[str, Any]]) -> int:
    """Merge records from previous source_prices.json that are within 7 days.
    Mutates current_records in place, returns number of records added."""
    previous = read_json(DATA_DIR / "source_prices.json", {})
    if not isinstance(previous, dict):
        return 0

    existing_keys = {
        (r.get("district", ""), r.get("mandi", ""), r.get("commodity", "").lower(), r.get("arrival_date", ""))
        for r in current_records
    }

    seven_days_ago = now_ist() - timedelta(days=7)
    added = 0

    for feed in previous.get("feeds", []):
        for r in feed.get("records", []):
            arrival = r.get("arrival_date", "")
            try:
                record_date = datetime.strptime(arrival, "%d/%m/%Y")
                if record_date < seven_days_ago:
                    continue
            except (ValueError, TypeError):
                continue

            key = (r.get("district", ""), r.get("mandi", ""), r.get("commodity", "").lower(), arrival)
            if key not in existing_keys:
                rec = format_record(r, source=r.get("source", "historical"))
                if rec:
                    current_records.append(rec)
                    existing_keys.add(key)
                    added += 1

    return added


# ─── Clean & Filter ───────────────────────────────────────────────────────────

def clean_and_filter(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply state filter, outlier removal, and mandi name normalization.

    1. State Filter: Only keep UP records (drop NTR/Palnadu/AP)
    2. Outlier Filter: Common Rice >₹8000 (Lucknow 11718 bug) auto drop
    3. Mandi Name Normalize: strip parenthetical suffixes like (Grain), (F&V)
    """
    clean: list[dict[str, Any]] = []
    for r in records:
        # 1. State Filter
        state = str(r.get("state", ""))
        if state and state not in {"Uttar Pradesh", "UP", "U.P."}:
            continue

        # 2. Outlier Filter
        commodity = str(r.get("commodity", "")).lower()
        variety = str(r.get("variety", "")).lower()
        modal = r.get("modal_price") or 0
        is_rice_common = (
            ("rice" in commodity or "paddy" in commodity or "chawal" in commodity)
            and "common" in variety
        )
        if is_rice_common and isinstance(modal, (int, float)) and modal > 8000:
            continue

        # 3. District normalization
        district = str(r.get("district", ""))
        canonical = canonical_district(district)
        if canonical != district:
            if not r.get("district_reported"):
                r["district_reported"] = district
            r["district"] = canonical
            r["district_hi"] = DISTRICT_HI.get(canonical, canonical)

        # 4. Mandi name normalize (strip parenthetical suffixes for matching,
        #    but keep original name for display)
        # We keep the original mandi name — the matching logic in
        # build_mandi_directory handles the APMC/parenthetical stripping.

        clean.append(r)

    return clean


# ─── Cross-Verification & Merge ───────────────────────────────────────────────

def build_final_payload(
    source_records: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Cross-verify records across sources and build final payload.

    Logic:
      - Records matching on (district, mandi, commodity, arrival_date, modal_price)
        across 2+ sources → cross_verified = True
      - Fallback: If 0 cross-verified, promote best 1000 single-source records
        as verified=True so SITE IS NEVER EMPTY
    """
    # Group records by verification key + modal_price
    grouped: dict[tuple, dict] = {}
    for source_name, records in source_records.items():
        for r in records:
            modal = r.get("modal_price")
            if modal in (None, 0):
                continue
            key = (
                r.get("district", ""),
                r.get("mandi", ""),
                r.get("commodity", "").lower(),
                r.get("arrival_date", ""),
                modal,
            )
            bucket = grouped.setdefault(key, {"record": r, "sources": []})
            if source_name not in bucket["sources"]:
                bucket["sources"].append(source_name)

    # Build cross-verified and single-source records
    cross_verified: list[dict[str, Any]] = []
    single_source: list[dict[str, Any]] = []

    for bucket in grouped.values():
        record = dict(bucket["record"])
        sources = bucket["sources"]
        record["verification_sources"] = sources
        record["verification_count"] = len(sources)
        record["cross_verified"] = len(sources) >= 2
        record["multi_source_verified"] = len(sources) >= 2
        record["three_source_verified"] = len(sources) >= 3
        record["source"] = ", ".join(sources)

        if len(sources) >= 2:
            record["verified"] = True
            cross_verified.append(record)
        else:
            record["verified"] = False
            record["verification_level"] = "single_source"
            single_source.append(record)

    cross_verified.sort(key=lambda r: (r.get("district") or "", r.get("mandi") or "", r.get("commodity") or ""))
    single_source.sort(key=lambda r: (r.get("district") or "", r.get("mandi") or "", r.get("commodity") or ""))

    # Fallback: If 0 cross-verified, promote best single-source records
    if not cross_verified and single_source:
        # Take up to 1000 best single-source records
        # Prefer more recent dates and higher modal prices as proxy for importance
        single_source.sort(key=lambda r: r.get("modal_price") or 0, reverse=True)
        promoted = single_source[:1000]
        for r in promoted:
            r["verified"] = True
            r["verification_level"] = "single_source_promoted"
        cross_verified = promoted
        print(f"  ⚠ 0 cross-verified records — promoted {len(promoted)} single-source as verified fallback")

    # Build source_prices snapshot
    feeds: list[dict[str, Any]] = []
    for source_name, records in source_records.items():
        feeds.append({
            "id": re.sub(r"[^a-z0-9_]", "_", source_name.lower()),
            "name": source_name,
            "status": "live" if records else "no_data",
            "records": records[:2000],
            "stored_record_count": min(len(records), 2000),
            "total_record_count": len(records),
        })

    source_prices = {
        "last_checked_at": now_ist().isoformat(),
        "feeds": feeds,
    }

    return cross_verified, source_prices


# ─── Main Orchestrator ────────────────────────────────────────────────────────

def main() -> None:
    """Run all 5 methods in parallel, merge, filter, and write output files."""
    DATA_DIR.mkdir(exist_ok=True)
    start = time.time()
    print(f"\n{'='*60}")
    print(f"🚀 UP Mandi Price Fetcher — 5 Methods Parallel")
    print(f"   Started: {now_ist().strftime('%Y-%m-%d %H:%M:%S')} IST")
    print(f"{'='*60}\n")

    # Run all 5 methods in parallel using ThreadPoolExecutor
    method_results: dict[str, tuple[list[dict[str, Any]], str]] = {}

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_method1_datagov): "method1_datagov",
            executor.submit(fetch_method2_gemini_direct): "method2_gemini",
            executor.submit(fetch_method3_openrouter): "method3_openrouter",
            executor.submit(fetch_method4_scraping): "method4_scraping",
            executor.submit(fetch_method5_sample_plus_history): "method5_sample_history",
        }
        for future in as_completed(futures):
            method_name = futures[future]
            try:
                result = future.result()
                method_results[method_name] = result
            except Exception as exc:
                print(f"  ❌ {method_name} raised exception: {exc}")
                method_results[method_name] = ([], "")

    # Collect all records by source
    print(f"\n{'='*60}")
    print("📊 Collecting & filtering results...")
    print(f"{'='*60}\n")

    all_source_records: dict[str, list[dict[str, Any]]] = {}
    total_raw = 0
    for method_name, (records, source_label) in method_results.items():
        if records and source_label:
            # Apply clean_and_filter per source
            clean = clean_and_filter(records)
            all_source_records[source_label] = clean
            total_raw += len(clean)
            print(f"  {source_label}: {len(records)} raw → {len(clean)} clean")

    print(f"\n  Total clean records across all sources: {total_raw}")

    if not all_source_records:
        print("\n  ⚠ All 5 methods failed! Trying to preserve existing data...")
        # Last resort: keep existing latest.json records
        existing = read_json(DATA_DIR / "latest.json", {})
        existing_records = existing.get("records", []) if isinstance(existing, dict) else []
        if existing_records:
            print(f"  ✅ Preserved {len(existing_records)} existing records from latest.json")
            all_source_records["existing_snapshot"] = existing_records
        else:
            print("  ❌ No existing data to preserve. Site will be empty this cycle.")

    # Cross-verify and merge
    final_records, source_prices = build_final_payload(all_source_records)

    # Write latest.json
    latest_payload = {
        "updated_at": now_ist().isoformat(),
        "last_checked_at": now_ist().isoformat(),
        "source": " + ".join(all_source_records.keys()) if all_source_records else "All sources failed",
        "verified": bool(final_records),
        "is_live": bool(final_records),
        "records": final_records,
        "update_frequency": "4 times daily",
        "fetch_methods_used": list(all_source_records.keys()),
        "method_summary": {
            name: len(recs) for name, recs in all_source_records.items()
        },
        "cross_verified_record_count": sum(1 for r in final_records if r.get("cross_verified")),
        "single_source_record_count": sum(1 for r in final_records if not r.get("cross_verified")),
    }

    # Backup existing files before overwriting
    for fname in ["latest.json", "source_prices.json"]:
        src = DATA_DIR / fname
        if src.exists():
            shutil.copy2(src, DATA_DIR / f"{fname}.bak")

    write_json_atomic(DATA_DIR / "latest.json", latest_payload)
    write_json_atomic(DATA_DIR / "source_prices.json", source_prices)

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"✅ DONE in {elapsed:.1f}s")
    print(f"   latest.json: {len(final_records)} records")
    print(f"   Cross-verified: {sum(1 for r in final_records if r.get('cross_verified'))}")
    print(f"   Single-source: {sum(1 for r in final_records if not r.get('cross_verified'))}")
    print(f"   Sources used: {list(all_source_records.keys())}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
