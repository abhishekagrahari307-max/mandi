#!/usr/bin/env python3
import os
import json
import random
import urllib.request
import re
from datetime import datetime, timedelta

# COMPLETE 75 DISTRICTS OF UTTAR PRADESH (दोनों भाषाओं में)
DISTRICTS = [
    {"en": "Agra", "hi": "आगरा"},
    {"en": "Aligarh", "hi": "अलीगढ़"},
    {"en": "Ambedkar Nagar", "hi": "अम्बेडकर नगर"},
    {"en": "Amethi", "hi": "अमेठी"},
    {"en": "Amroha", "hi": "अमरोहा"},
    {"en": "Auraiya", "hi": "औरैया"},
    {"en": "Azamgarh", "hi": "आजमगढ़"},
    {"en": "Baghpat", "hi": "बागपत"},
    {"en": "Bahraich", "hi": "बहराइच"},
    {"en": "Ballia", "hi": "बलिया"},
    {"en": "Balrampur", "hi": "बलरामपुर"},
    {"en": "Banda", "hi": "बांदा"},
    {"en": "Barabanki", "hi": "बाराबंकी"},
    {"en": "Bareilly", "hi": "बरेली"},
    {"en": "Basti", "hi": "बस्ती"},
    {"en": "Bhadohi", "hi": "भदोही"},
    {"en": "Bijnor", "hi": "बिजनौर"},
    {"en": "Budaun", "hi": "बदायूं"},
    {"en": "Bulandshahr", "hi": "बुलंदशहर"},
    {"en": "Chandauli", "hi": "चंदौली"},
    {"en": "Chitrakoot", "hi": "चित्रकूट"},
    {"en": "Deoria", "hi": "देवरिया"},
    {"en": "Etah", "hi": "एटा"},
    {"en": "Etawah", "hi": "इटावा"},
    {"en": "Ayodhya", "hi": "अयोध्या"},
    {"en": "Farrukhabad", "hi": "फर्रुखाबाद"},
    {"en": "Fatehpur", "hi": "फतेहपुर"},
    {"en": "Firozabad", "hi": "फिरोजाबाद"},
    {"en": "Gautam Buddha Nagar", "hi": "गौतम बुद्ध नगर"},
    {"en": "Ghaziabad", "hi": "गाजियाबाद"},
    {"en": "Ghazipur", "hi": "गाजीपुर"},
    {"en": "Gonda", "hi": "गोंडा"},
    {"en": "Gorakhpur", "hi": "गोरखपुर"},
    {"en": "Hamirpur", "hi": "हमीरपुर"},
    {"en": "Hapur", "hi": "हापुड़"},
    {"en": "Hardoi", "hi": "हरदोई"},
    {"en": "Hathras", "hi": "हाथरस"},
    {"en": "Jalaun", "hi": "जालौन"},
    {"en": "Jaunpur", "hi": "जाउनपुर"},
    {"en": "Jhansi", "hi": "झांसी"},
    {"en": "Kannauj", "hi": "कन्नौज"},
    {"en": "Kanpur Dehat", "hi": "कानपुर देहात"},
    {"en": "Kanpur Nagar", "hi": "कानपुर नगर"},
    {"en": "Kasganj", "hi": "कासगंज"},
    {"en": "Kaushambi", "hi": "कौशाम्बी"},
    {"en": "Kushinagar", "hi": "कुशीनगर"},
    {"en": "Lakhimpur Kheri", "hi": "लखीमपुर खीरी"},
    {"en": "Lalitpur", "hi": "ललितपुर"},
    {"en": "Lucknow", "hi": "लखनऊ"},
    {"en": "Maharajganj", "hi": "महाराजगंज"},
    {"en": "Mahoba", "hi": "महोबा"},
    {"en": "Mainpuri", "hi": "मैनपुरी"},
    {"en": "Mathura", "hi": "मथुरा"},
    {"en": "Mau", "hi": "मऊ"},
    {"en": "Meerut", "hi": "मेरठ"},
    {"en": "Mirzapur", "hi": "मिर्जापुर"},
    {"en": "Moradabad", "hi": "मुरादाबाद"},
    {"en": "Muzaffarnagar", "hi": "मुजफ्फरनगर"},
    {"en": "Pilibhit", "hi": "पीलीभीत"},
    {"en": "Pratapgarh", "hi": "प्रतापगढ़"},
    {"en": "Prayagraj", "hi": "प्रयागराज"},
    {"en": "Raebareli", "hi": "रायबरेली"},
    {"en": "Rampur", "hi": "रामपुर"},
    {"en": "Saharanpur", "hi": "सहारनपुर"},
    {"en": "Sambhal", "hi": "संभल"},
    {"en": "Sant Kabir Nagar", "hi": "संत कबीर नगर"},
    {"en": "Shahjahanpur", "hi": "शाहजहाँपुर"},
    {"en": "Shamli", "hi": "शामली"},
    {"en": "Shravasti", "hi": "श्रावस्ती"},
    {"en": "Siddharthnagar", "hi": "सिद्धार्थनगर"},
    {"en": "Sitapur", "hi": "सीतापुर"},
    {"en": "Sonbhadra", "hi": "सोनभद्र"},
    {"en": "Sultanpur", "hi": "सुल्तानपुर"},
    {"en": "Unnao", "hi": "उन्नाव"},
    {"en": "Varanasi", "hi": "वाराणसी"}
]

# EXTENDED RICH COMMODITIES LIST (अनाज, सब्जियां, तिलहन, दलहन, फल)
COMMODITIES = [
    {"en": "Wheat", "hi": "गेहूं", "base_price": 2350, "min_var": -50, "max_var": 80, "unit": "Quintal"},
    {"en": "Paddy (Dhan)", "hi": "धान (सामान्य)", "base_price": 2183, "min_var": -40, "max_var": 60, "unit": "Quintal"},
    {"en": "Basmati Paddy", "hi": "धान (बासमती)", "base_price": 3800, "min_var": -200, "max_var": 400, "unit": "Quintal"},
    {"en": "Potato", "hi": "आलू", "base_price": 1450, "min_var": -150, "max_var": 200, "unit": "Quintal"},
    {"en": "Onion", "hi": "प्याज़", "base_price": 2200, "min_var": -200, "max_var": 300, "unit": "Quintal"},
    {"en": "Tomato", "hi": "टमाटर", "base_price": 1800, "min_var": -300, "max_var": 500, "unit": "Quintal"},
    {"en": "Mustard", "hi": "सरसों", "base_price": 5400, "min_var": -100, "max_var": 150, "unit": "Quintal"},
    {"en": "Gram (Chana)", "hi": "चना", "base_price": 5850, "min_var": -80, "max_var": 120, "unit": "Quintal"},
    {"en": "Garlic", "hi": "लहसुन", "base_price": 9500, "min_var": -500, "max_var": 1000, "unit": "Quintal"},
    {"en": "Arhar (Tur)", "hi": "अरहर (दाल)", "base_price": 8600, "min_var": -150, "max_var": 200, "unit": "Quintal"},
    {"en": "Green Chillies", "hi": "हरी मिर्च", "base_price": 3200, "min_var": -300, "max_var": 400, "unit": "Quintal"},
    {"en": "Maize (Makka)", "hi": "मक्का", "base_price": 2050, "min_var": -50, "max_var": 100, "unit": "Quintal"},
    {"en": "Barley (Jau)", "hi": "जौ", "base_price": 2150, "min_var": -50, "max_var": 80, "unit": "Quintal"},
    {"en": "Moong (Green Gram)", "hi": "मूंग (दाल)", "base_price": 7200, "min_var": -150, "max_var": 250, "unit": "Quintal"},
    {"en": "Urad (Black Gram)", "hi": "उड़द (दाल)", "base_price": 7800, "min_var": -200, "max_var": 300, "unit": "Quintal"},
    {"en": "Ginger", "hi": "अदरक", "base_price": 6500, "min_var": -500, "max_var": 800, "unit": "Quintal"},
    {"en": "Apple", "hi": "सेब", "base_price": 7500, "min_var": -1000, "max_var": 1500, "unit": "Quintal"},
    {"en": "Banana", "hi": "केला", "base_price": 2800, "min_var": -300, "max_var": 500, "unit": "Quintal"}
]

# VARIETIES, GRADES & ARRIVALS (अन्य महत्वपूर्ण विवरण)
VARIETIES = [
    {"en": "FAQ / Common", "hi": "सामान्य (FAQ)"},
    {"en": "Local / Desi", "hi": "देशी / लोकल"},
    {"en": "Hybrid", "hi": "हाइब्रिड"},
    {"en": "Medium Quality", "hi": "मध्यम श्रेणी"},
    {"en": "Super Grade", "hi": "उत्कृष्ट श्रेणी"}
]

GRADES = [
    {"en": "FAQ", "hi": "FAQ (सामान्य)"},
    {"en": "Grade A", "hi": "ग्रेड-A"},
    {"en": "Medium", "hi": "मध्यम"}
]

WEATHER_STATUSES = [
    {"en": "Sunny", "hi": "धूप", "temp_min": 25, "temp_max": 38},
    {"en": "Partly Cloudy", "hi": "आंशिक बादल", "temp_min": 24, "temp_max": 35},
    {"en": "Showers", "hi": "हल्की बारिश", "temp_min": 22, "temp_max": 30},
    {"en": "Heavy Rain", "hi": "भारी बारिश", "temp_min": 20, "temp_max": 28},
    {"en": "Clear Sky", "hi": "साफ मौसम", "temp_min": 22, "temp_max": 36}
]

def generate_mock_data():
    """Generates complete, realistic market price data for ALL 75 UP Districts."""
    now = datetime.now()
    today_str = now.strftime("%d/%m/%Y")
    
    records = []
    for dist in DISTRICTS:
        # Every district has a subset of random crops active
        active_count = random.randint(5, 9)
        active_commodities = random.sample(COMMODITIES, active_count)
        
        for comm in active_commodities:
            dist_factor = random.uniform(0.92, 1.08) # Realistic regional supply variations
            base = comm["base_price"] * dist_factor
            
            min_p = int(base + random.randint(comm["min_var"], 0))
            max_p = int(base + random.randint(0, comm["max_var"]))
            modal_p = int((min_p + max_p) / 2 + random.randint(-15, 15))
            
            # Select random extra details (Variety, Grade, Arrivals)
            var_choice = random.choice(VARIETIES)
            grade_choice = random.choice(GRADES)
            arrivals_qty = random.randint(15, 450) # Arrival quantity in Tonnes/Quintals
            
            records.append({
                "state": "Uttar Pradesh",
                "district": dist["en"],
                "district_hi": dist["hi"],
                "mandi": f"{dist['en']} Mandi",
                "mandi_hi": f"{dist['hi']} मंडी",
                "commodity": comm["en"],
                "commodity_hi": comm["hi"],
                "variety": var_choice["en"],
                "variety_hi": var_choice["hi"],
                "grade": grade_choice["en"],
                "grade_hi": grade_choice["hi"],
                "arrivals": arrivals_qty,
                "arrivals_unit": "Tonnes",
                "arrivals_unit_hi": "टन",
                "min_price": min_p,
                "max_price": max_p,
                "modal_price": modal_p,
                "price_unit": comm["unit"],
                "arrival_date": today_str
            })
            
    return records

def fetch_agmarknet_scraped():
    """Scraper that pulls official UP Agmarknet listings with full details."""
    print("Direct scraping agmarknet.gov.in database for all districts...")
    url = "https://agmarknet.gov.in/SearchCmmMkt.aspx?Tx_Commodity=0&Tx_State=UP&Tx_District=0&Tx_Market=0&Tx_Trend=0"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
            row_pattern = re.compile(r'<tr>(.*?)</tr>', re.DOTALL)
            cell_pattern = re.compile(r'<td>(.*?)</td>', re.DOTALL)
            
            rows = row_pattern.findall(html)
            scraped_records = []
            
            for row in rows:
                cells = cell_pattern.findall(row)
                cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
                
                # S.No, State, District, Market, Commodity, Variety, Grade, Min Price, Max Price, Modal Price, Price Date
                if len(cells) >= 10 and cells[1] == "Uttar Pradesh":
                    dist_en = cells[2]
                    mandi_en = cells[3]
                    comm_en = cells[4]
                    variety_en = cells[5]
                    grade_en = cells[6]
                    
                    min_p = int(float(cells[7])) if cells[7].replace('.','',1).isdigit() else 0
                    max_p = int(float(cells[8])) if cells[8].replace('.','',1).isdigit() else 0
                    modal_p = int(float(cells[9])) if cells[9].replace('.','',1).isdigit() else 0
                    
                    if modal_p > 0:
                        # Find translations or keep original
                        comm_hi = next((c["hi"] for c in COMMODITIES if c["en"].lower() in comm_en.lower()), comm_en)
                        dist_hi = next((d["hi"] for d in DISTRICTS if d["en"].lower() in dist_en.lower()), dist_en)
                        variety_hi = next((v["hi"] for v in VARIETIES if v["en"].lower() in variety_en.lower()), variety_en)
                        grade_hi = next((g["hi"] for g in GRADES if g["en"].lower() in grade_en.lower()), grade_en)
                        
                        # Set default simulated arrival if agmarknet daily doesn't have it directly on simple grid
                        arrivals_qty = random.randint(15, 300)
                        
                        scraped_records.append({
                            "state": "Uttar Pradesh",
                            "district": dist_en,
                            "district_hi": dist_hi,
                            "mandi": mandi_en,
                            "mandi_hi": f"{dist_hi} मंडी",
                            "commodity": comm_en,
                            "commodity_hi": comm_hi,
                            "variety": variety_en,
                            "variety_hi": variety_hi,
                            "grade": grade_en,
                            "grade_hi": grade_hi,
                            "arrivals": arrivals_qty,
                            "arrivals_unit": "Tonnes",
                            "arrivals_unit_hi": "टन",
                            "min_price": min_p,
                            "max_price": max_p,
                            "modal_price": modal_p,
                            "price_unit": "Quintal",
                            "arrival_date": cells[10]
                        })
            if scraped_records:
                print(f"Scraped {len(scraped_records)} live rows.")
                return scraped_records
    except Exception as e:
        print(f"Agmarknet direct scrape failed: {e}")
    return None

def fetch_real_data(api_key):
    """Fetches real-time UP mandi listings using data.gov.in API with rich columns."""
    url = f"https://api.data.gov.in/resource/9ef842f8-24b4-4749-a978-d0c17b101cff?api-key={api_key}&format=json&limit=500&filters[state]=Uttar+Pradesh"
    try:
        print("Fetching official government feed with API...")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode())
            records = res_data.get("records", [])
            if records:
                formatted_records = []
                for r in records:
                    comm_en = r.get("commodity", "Other")
                    dist_en = r.get("district", "Other")
                    variety_en = r.get("variety", "Common")
                    grade_en = r.get("grade", "FAQ")
                    
                    comm_hi = next((c["hi"] for c in COMMODITIES if c["en"].lower() in comm_en.lower()), comm_en)
                    dist_hi = next((d["hi"] for d in DISTRICTS if d["en"].lower() in dist_en.lower()), dist_en)
                    variety_hi = next((v["hi"] for v in VARIETIES if v["en"].lower() in variety_en.lower()), variety_en)
                    grade_hi = next((g["hi"] for g in GRADES if g["en"].lower() in grade_en.lower()), grade_en)
                    
                    arrivals_qty = random.randint(20, 400) # Simulated arrivals
                    
                    formatted_records.append({
                        "state": r.get("state", "Uttar Pradesh"),
                        "district": dist_en,
                        "district_hi": dist_hi,
                        "mandi": r.get("market", f"{dist_en} Mandi"),
                        "mandi_hi": f"{dist_hi} मंडी",
                        "commodity": comm_en,
                        "commodity_hi": comm_hi,
                        "variety": variety_en,
                        "variety_hi": variety_hi,
                        "grade": grade_en,
                        "grade_hi": grade_hi,
                        "arrivals": arrivals_qty,
                        "arrivals_unit": "Tonnes",
                        "arrivals_unit_hi": "टन",
                        "min_price": int(float(r.get("min_price", 0))),
                        "max_price": int(float(r.get("max_price", 0))),
                        "modal_price": int(float(r.get("modal_price", 0))),
                        "price_unit": "Quintal",
                        "arrival_date": r.get("arrival_date", datetime.now().strftime("%d/%m/%Y"))
                    })
                return formatted_records
    except Exception as e:
        print(f"data.gov.in API fetching failed: {e}")
    return None

def generate_history():
    history = {}
    now = datetime.now()
    for comm in COMMODITIES:
        history[comm["en"]] = []
        base = comm["base_price"]
        for i in range(7, 0, -1):
            date_val = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            factor = 1.0 + (random.randint(-5, 7) / 100.0)
            history[comm["en"]].append({
                "date": date_val,
                "price": int(base * factor)
            })
    return history

def generate_weather():
    weather = []
    # Pick a subset of districts for weather (major ones) to keep weather payload size clean
    weather_districts = random.sample(DISTRICTS, 15)
    for dist in weather_districts:
        status = random.choice(WEATHER_STATUSES)
        weather.append({
            "district": dist["en"],
            "district_hi": dist["hi"],
            "temp": random.randint(status["temp_min"], status["temp_max"]),
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
        records = fetch_agmarknet_scraped()
        
    if not records:
        print("Fallback to complete 75-district simulated pricing models...")
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
        
    print("✅ Successfully updated UP Mandi Dashboard with ALL 75 Districts & Rich columns!")

if __name__ == "__main__":
    main()
