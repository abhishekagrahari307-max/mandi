#!/usr/bin/env python3
import os
import json
import random
import urllib.request
from datetime import datetime, timedelta

# Configurations
DISTRICTS = [
    {"en": "Kanpur", "hi": "कानपुर"},
    {"en": "Lucknow", "hi": "लखनऊ"},
    {"en": "Varanasi", "hi": "वाराणसी"},
    {"en": "Agra", "hi": "आगरा"},
    {"en": "Meerut", "hi": "मेरठ"},
    {"en": "Prayagraj", "hi": "प्रयागराज"},
    {"en": "Bareilly", "hi": "बरेली"},
    {"en": "Gorakhpur", "hi": "गोरखपुर"},
    {"en": "Aligarh", "hi": "अलीगढ़"},
    {"en": "Jhansi", "hi": "झांसी"},
    {"en": "Hapur", "hi": "हापुड़"},
    {"en": "Shahjahanpur", "hi": "शाहजहाँपुर"}
]

COMMODITIES = [
    {"en": "Wheat", "hi": "गेहूं", "base_price": 2350, "min_var": -50, "max_var": 80, "unit": "Quintal"},
    {"en": "Paddy (Dhan)", "hi": "धान (common)", "base_price": 2183, "min_var": -40, "max_var": 60, "unit": "Quintal"},
    {"en": "Potato", "hi": "आलू", "base_price": 1450, "min_var": -150, "max_var": 200, "unit": "Quintal"},
    {"en": "Onion", "hi": "प्याज़", "base_price": 2200, "min_var": -200, "max_var": 300, "unit": "Quintal"},
    {"en": "Tomato", "hi": "टमाटर", "base_price": 1800, "min_var": -300, "max_var": 500, "unit": "Quintal"},
    {"en": "Mustard", "hi": "सरसों", "base_price": 5400, "min_var": -100, "max_var": 150, "unit": "Quintal"},
    {"en": "Gram (Chana)", "hi": "चना", "base_price": 5850, "min_var": -80, "max_var": 120, "unit": "Quintal"},
    {"en": "Garlic", "hi": "लहसुन", "base_price": 9500, "min_var": -500, "max_var": 1000, "unit": "Quintal"},
    {"en": "Arhar (Tur)", "hi": "अरहर (दाल)", "base_price": 8600, "min_var": -150, "max_var": 200, "unit": "Quintal"},
    {"en": "Green Chillies", "hi": "हरी मिर्च", "base_price": 3200, "min_var": -300, "max_var": 400, "unit": "Quintal"}
]

WEATHER_STATUSES = [
    {"en": "Sunny", "hi": "धूप", "temp_min": 25, "temp_max": 38},
    {"en": "Partly Cloudy", "hi": "आंशिक बादल", "temp_min": 24, "temp_max": 35},
    {"en": "Showers", "hi": "हल्की बारिश", "temp_min": 22, "temp_max": 30},
    {"en": "Heavy Rain", "hi": "भारी बारिश", "temp_min": 20, "temp_max": 28},
    {"en": "Clear Sky", "hi": "साफ मौसम", "temp_min": 22, "temp_max": 36}
]

def generate_mock_data():
    """Generates realistic market price data for UP Mandis."""
    now = datetime.now()
    today_str = now.strftime("%d/%m/%Y")
    
    records = []
    # Generate prices for combinations
    for dist in DISTRICTS:
        # Each mandi has random subset of commodities active
        active_count = random.randint(6, len(COMMODITIES))
        active_commodities = random.sample(COMMODITIES, active_count)
        
        for comm in active_commodities:
            # Add some variations based on district characteristics
            # e.g., Agra/Kanpur potatoes are slightly cheaper due to high supply
            dist_factor = 1.0
            if dist["en"] in ["Agra", "Kanpur"] and comm["en"] == "Potato":
                dist_factor = 0.9
            
            base = comm["base_price"] * dist_factor
            min_p = int(base + random.randint(comm["min_var"], 0))
            max_p = int(base + random.randint(0, comm["max_var"]))
            modal_p = int((min_p + max_p) / 2 + random.randint(-20, 20))
            
            records.append({
                "state": "Uttar Pradesh",
                "district": dist["en"],
                "district_hi": dist["hi"],
                "mandi": f"{dist['en']} Mandi",
                "mandi_hi": f"{dist['hi']} मंडी",
                "commodity": comm["en"],
                "commodity_hi": comm["hi"],
                "variety": "Local / Common",
                "grade": "FAQ",
                "min_price": min_p,
                "max_price": max_p,
                "modal_price": modal_p,
                "price_unit": comm["unit"],
                "arrival_date": today_str
            })
            
    return records

def fetch_real_data(api_key):
    """Attempts to fetch real agricultural commodity rates from data.gov.in API."""
    url = f"https://api.data.gov.in/resource/9ef842f8-24b4-4749-a978-d0c17b101cff?api-key={api_key}&format=json&limit=200&filters[state]=Uttar+Pradesh"
    try:
        print("Fetching real-time UP Mandi data from data.gov.in...")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode())
            records = res_data.get("records", [])
            if records:
                print(f"Successfully fetched {len(records)} records from API.")
                # Format to our schema with Hindi translations
                formatted_records = []
                for r in records:
                    # Map English names to Hindi equivalent
                    comm_en = r.get("commodity", "Other")
                    dist_en = r.get("district", "Other")
                    
                    # Find matching Hindi terms or default
                    comm_hi = next((c["hi"] for c in COMMODITIES if c["en"].lower() in comm_en.lower()), comm_en)
                    dist_hi = next((d["hi"] for d in DISTRICTS if d["en"].lower() in dist_en.lower()), dist_en)
                    
                    formatted_records.append({
                        "state": r.get("state", "Uttar Pradesh"),
                        "district": dist_en,
                        "district_hi": dist_hi,
                        "mandi": r.get("market", f"{dist_en} Mandi"),
                        "mandi_hi": f"{dist_hi} मंडी",
                        "commodity": comm_en,
                        "commodity_hi": comm_hi,
                        "variety": r.get("variety", "Common"),
                        "grade": r.get("grade", "FAQ"),
                        "min_price": int(float(r.get("min_price", 0))),
                        "max_price": int(float(r.get("max_price", 0))),
                        "modal_price": int(float(r.get("modal_price", 0))),
                        "price_unit": "Quintal",
                        "arrival_date": r.get("arrival_date", datetime.now().strftime("%d/%m/%Y"))
                    })
                return formatted_records
    except Exception as e:
        print(f"Error fetching from data.gov.in: {e}. Falling back to smart mock data.")
    return None

def generate_history():
    """Generates 7-day historical price points for trend analysis."""
    history = {}
    now = datetime.now()
    
    for comm in COMMODITIES:
        history[comm["en"]] = []
        base = comm["base_price"]
        for i in range(7, 0, -1):
            date_val = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            # Create a random walk for prices
            factor = 1.0 + (random.randint(-5, 7) / 100.0)
            avg_price = int(base * factor)
            history[comm["en"]].append({
                "date": date_val,
                "price": avg_price
            })
    return history

def generate_weather():
    """Generates weather data for main agricultural areas in UP."""
    weather = []
    for dist in DISTRICTS:
        status = random.choice(WEATHER_STATUSES)
        temp = random.randint(status["temp_min"], status["temp_max"])
        weather.append({
            "district": dist["en"],
            "district_hi": dist["hi"],
            "temp": temp,
            "status": status["en"],
            "status_hi": status["hi"],
            "humidity": random.randint(45, 90),
            "wind": random.randint(5, 20)
        })
    return weather

def main():
    os.makedirs("data", exist_ok=True)
    
    api_key = os.environ.get("DATA_GOV_IN_API_KEY", "")
    records = None
    
    if api_key:
        records = fetch_real_data(api_key)
        
    if not records:
        records = generate_mock_data()
        
    history = generate_history()
    weather = generate_weather()
    
    # Save files
    with open("data/latest.json", "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now().isoformat(),
            "records": records
        }, f, ensure_ascii=False, indent=2)
        
    with open("data/history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
        
    with open("data/weather.json", "w", encoding="utf-8") as f:
        json.dump(weather, f, ensure_ascii=False, indent=2)
        
    print("✅ Successfully updated UP Mandi Dashboard data structures!")

if __name__ == "__main__":
    main()
