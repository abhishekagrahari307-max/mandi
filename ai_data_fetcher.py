#!/usr/bin/env python3
"""AI-powered data fetcher for AGMARKNET, e-NAM, and UP e-Mandi portals.

Uses OpenRouter API with Gemini (web-grounding capable) to scrape real-time
mandi price data from government portals that block direct HTTP access.

The AI model visits the portal, extracts structured price data, and returns
it as JSON that gets merged into the dashboard data files.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Gemini 2.0 Flash has web grounding / browsing capability.
# Prefer the primary configured model, but fall back across a small list so a
# temporarily rate-limited/unavailable `:free` model never stops the whole fetch.
AI_MODELS = [
    os.environ.get("OPENROUTER_VISION_MODEL", "google/gemini-2.0-flash-exp:free"),
    "google/gemini-2.0-flash-exp:free",
    "google/gemini-2.5-flash",
    "openai/gpt-4o-mini",
]
AI_TIMEOUT = 90  # seconds


def _call_ai(system_prompt: str, user_prompt: str, api_key: str) -> str:
    """Call OpenRouter AI and return the text response (with retry + fallback)."""
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://abhishekagrahari307-max.github.io/mandi/",
        "X-Title": "UP Mandi Dashboard AI Fetcher",
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
            resp = urllib.request.urlopen(req, timeout=AI_TIMEOUT)
            payload = json.loads(resp.read().decode("utf-8"))
            choices = payload.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            error = payload.get("error", {})
            last_error = f"model={model} no choices: {error}"
            print(f"  ⚠ AI model {model} returned no choices, trying fallback...")
        except Exception as exc:
            last_error = f"model={model} failed: {exc}"
            print(f"  ⚠ AI model {model} call failed ({exc}), trying fallback...")

    raise RuntimeError(f"OpenRouter API call failed across all models. Last error: {last_error}")


def _parse_json_from_response(text: str) -> list[dict[str, Any]]:
    """Extract JSON array from AI response text."""
    # Try to find a JSON array in the response
    # Look for ```json ... ``` code blocks first
    code_block = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find a raw JSON array
    json_match = re.search(r"\[[\s\S]*\]", text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return []


def fetch_agmarknet_up(api_key: str) -> list[dict[str, Any]]:
    """Fetch UP mandi prices from AGMARKNET using AI web browsing.

    AGMARKNET (agmarknet.gov.in) blocks direct HTTP scraping with 403.
    We use Gemini's web grounding to visit the portal and extract today's
    Uttar Pradesh mandi prices.
    """
    today = datetime.now(IST).strftime("%d/%m/%Y")
    system = (
        "You are a mandi price data extractor. Visit the AGMARKNET portal "
        "(agmarknet.gov.in) and extract today's Uttar Pradesh mandi prices. "
        "Return ONLY a JSON array of objects. Each object must have these exact keys:\n"
        '  "district", "market", "commodity", "variety", "grade", '
        '  "min_price" (number), "max_price" (number), "modal_price" (number), '
        '  "arrival_date" (DD/MM/YYYY format).\n'
        "Do NOT include any explanation, markdown, or commentary. Only return the JSON array."
    )
    user = (
        f"Today is {today}. Search for Uttar Pradesh mandi prices on AGMARKNET "
        f"(https://agmarknet.gov.in/SearchCmmMkt.aspx?Tx_Commodity=0&Tx_State=UP"
        f"&Tx_District=0&Tx_Market=0&Tx_Trend=0). "
        f"Extract ALL available commodity prices from ALL UP mandis for today ({today}). "
        f"Include Wheat (गेहूं), Rice (चावल), Paddy, Potato, Onion, and all other commodities. "
        f"Return as JSON array. Prices should be in Rupees per Quintal."
    )

    try:
        response = _call_ai(system, user, api_key)
        records = _parse_json_from_response(response)
        # Validate and normalize records
        valid = []
        for r in records:
            if not isinstance(r, dict):
                continue
            if not r.get("district") or not r.get("market") or not r.get("commodity"):
                continue
            if not isinstance(r.get("modal_price"), (int, float)):
                continue
            r["state"] = "Uttar Pradesh"
            r.setdefault("arrival_date", today)
            r.setdefault("variety", "Other")
            r.setdefault("grade", "FAQ")
            valid.append(r)
        print(f"  ✅ AGMARKNET AI fetch: {len(valid)} records extracted")
        return valid
    except Exception as exc:
        print(f"  ⚠ AGMARKNET AI fetch failed: {exc}")
        return []


def fetch_enam_up(api_key: str) -> list[dict[str, Any]]:
    """Fetch UP mandi trade data from e-NAM portal using AI web browsing.

    e-NAM (enam.gov.in) requires authorized API access which is not configured.
    We use AI to scrape the public dashboard for UP trade data.
    """
    today = datetime.now(IST).strftime("%d/%m/%Y")
    system = (
        "You are a mandi trade data extractor. Visit the e-NAM portal "
        "(enam.gov.in) and extract Uttar Pradesh mandi trade data. "
        "Return ONLY a JSON array of objects with keys:\n"
        '  "district", "market", "commodity", "variety", "grade", '
        '  "min_price" (number), "max_price" (number), "modal_price" (number), '
        '  "arrival_date" (DD/MM/YYYY), "arrivals" (quintals, number or null).\n'
        "Do NOT include any explanation. Only return the JSON array."
    )
    user = (
        f"Today is {today}. Search for Uttar Pradesh trade data on e-NAM "
        f"(https://enam.gov.in/web/dashboard/trade-data). "
        f"Extract ALL available commodity prices from UP mandis for today. "
        f"Focus on Wheat, Rice, Paddy, and other major crops. "
        f"Return as JSON array with prices in Rupees per Quintal."
    )

    try:
        response = _call_ai(system, user, api_key)
        records = _parse_json_from_response(response)
        valid = []
        for r in records:
            if not isinstance(r, dict):
                continue
            if not r.get("district") or not r.get("commodity"):
                continue
            if not isinstance(r.get("modal_price"), (int, float)):
                continue
            r["state"] = "Uttar Pradesh"
            r.setdefault("arrival_date", today)
            r.setdefault("variety", "Other")
            r.setdefault("grade", "FAQ")
            valid.append(r)
        print(f"  ✅ e-NAM AI fetch: {len(valid)} records extracted")
        return valid
    except Exception as exc:
        print(f"  ⚠ e-NAM AI fetch failed: {exc}")
        return []


def fetch_up_emandi(api_key: str) -> list[dict[str, Any]]:
    """Fetch UP mandi prices from UP e-Mandi portal using AI web browsing.

    UP e-Mandi (emandi.up.gov.in) requires authorized API access.
    We use AI to scrape the public-facing portal for price data.
    """
    today = datetime.now(IST).strftime("%d/%m/%Y")
    system = (
        "You are a UP mandi price extractor. Visit the UP e-Mandi portal "
        "(emandi.up.gov.in) and extract today's mandi prices. "
        "Return ONLY a JSON array of objects with keys:\n"
        '  "district", "market", "commodity", "variety", "grade", '
        '  "min_price" (number), "max_price" (number), "modal_price" (number), '
        '  "arrival_date" (DD/MM/YYYY).\n'
        "Do NOT include any explanation. Only return the JSON array."
    )
    user = (
        f"Today is {today}. Search for Uttar Pradesh mandi prices on UP e-Mandi "
        f"(https://emandi.up.gov.in/). "
        f"Extract ALL available commodity prices from ALL UP mandis for today ({today}). "
        f"Focus especially on Wheat (गेहूं), Rice (चावल), Paddy, Potato, Onion. "
        f"Return as JSON array with prices in Rupees per Quintal."
    )

    try:
        response = _call_ai(system, user, api_key)
        records = _parse_json_from_response(response)
        valid = []
        for r in records:
            if not isinstance(r, dict):
                continue
            if not r.get("district") or not r.get("commodity"):
                continue
            if not isinstance(r.get("modal_price"), (int, float)):
                continue
            r["state"] = "Uttar Pradesh"
            r.setdefault("arrival_date", today)
            r.setdefault("variety", "Other")
            r.setdefault("grade", "FAQ")
            valid.append(r)
        print(f"  ✅ UP e-Mandi AI fetch: {len(valid)} records extracted")
        return valid
    except Exception as exc:
        print(f"  ⚠ UP e-Mandi AI fetch failed: {exc}")
        return []


def fetch_all_ai_sources(api_key: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """Fetch data from all AI-scraped sources.

    Returns a dict mapping source_id to list of raw records:
        {
            "agmarknet_ai": [...],
            "enam_ai": [...],
            "up_emandi_ai": [...]
        }
    """
    key = api_key or os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        print("  ⚠ OPENROUTER_API_KEY not configured — AI fetch skipped")
        return {}

    print("🤖 Fetching data via AI (Gemini web browsing)...")
    results: dict[str, list[dict[str, Any]]] = {}

    results["agmarknet_ai"] = fetch_agmarknet_up(key)
    results["enam_ai"] = fetch_enam_up(key)
    results["up_emandi_ai"] = fetch_up_emandi(key)

    total = sum(len(v) for v in results.values())
    print(f"  📊 Total AI-fetched records: {total}")
    return results
