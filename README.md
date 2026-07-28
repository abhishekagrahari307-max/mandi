# 🌾 उत्तर प्रदेश लाइव मंडी भाव — UP Mandi Dashboard

एक आधुनिक, सुंदर, तेज और मोबाइल-फ्रेंडली (PWA) वेब एप्लिकेशन जो उत्तर प्रदेश की सभी बड़ी मंडियों के दैनिक कृषि भाव (गेहूं, धान, आलू, प्याज, टमाटर, आदि) को प्रदर्शित करता है।

यह प्रोजेक्ट **Vijay Kumar Traders** की डिजिटल सेवा के रूप में डिज़ाइन किया गया है।

---

## ✨ मुख्य विशेषताएं (Key Features)

- **🌐 पूर्णतः द्विभाषी (Bilingual):** एक क्लिक में हिन्दी और English के बीच बदलें।
- **📱 PWA इंस्टॉल करें (Add to Home Screen):** इसे फोन में इंस्टॉल करके बिना इंटरनेट (Offline Mode) के भी पुराने भाव देख सकते हैं।
- **🧮 मंडी बिल कैलकुलेटर (Interactive Calculator):** कुल वजन, भाव, आढ़त कमीशन, मजदूरी/पल्लेदारी, मंडी टैक्स और भाड़ा घटाकर किसान/व्यापारी का शुद्ध भुगतान (Net Payout) सेकंडों में निकालें।
- **🏷️ स्रोत-वार सरकारी भाव:** data.gov.in, AGMARKNET, e-NAM और UP e-Mandi के अपने-अपने reported भाव अलग cards में देखें—कोई mixing या averaging नहीं।
- **📈 सत्यापित मूल्य ग्राफ (Verified Price Trends):** सफल सरकारी snapshots से बने वास्तविक ऐतिहासिक भाव देखें।
- **🕒 भाव अपडेट समय बार (Header):** हर पेज के ऊपर साफ दिखता है कि भाव **कब** अपडेट हुआ, portals की **अंतिम जाँच** कब हुई, **अगला अपडेट** कब है और दैनिक IST slots क्या हैं।
- **📍 जिला नाम सुधार (District normalisation):** Allahabad→Prayagraj, Faizabad→Ayodhya, Bara Banki→Barabanki, Bhadohi→Sant Ravidas Nagar जैसी सरकारी वर्तनी/नाम-परिवर्तन अपने-आप एक ही जनपद में मिलाए जाते हैं, ताकि हर जिले का सही हिन्दी नाम दिखे और अलग-अलग feeds का मिलान हो सके।
- **🏛️ पूरी मंडी निर्देशिका:** मंडी, जिला, जिंस, भाव सीमा, उपलब्ध स्थानीय अधिकारी संपर्क, केंद्रीय helpdesk और official links।
- **⚖️ अधिनियम और नियमावली:** U.P. Krishi Utpadan Mandi Adhiniyam 1964, Niyamawali 1965, अध्याय और धारा-सूची के official India Code links।
- **🔨 e-NAM नीलामी:** अधिकृत feed मिलने पर जिला एवं lot-wise read-only live snapshot; वास्तविक bid केवल authenticated e-NAM portal पर। कोई simulated lot/bid नहीं।
- **🗺️ राज्य-वार भाव:** केवल 3+ सरकारी feeds पर match हुए records से राज्य, जिला, मंडी और जिंस का सारांश।
- **🏢 मण्डी परिषद निर्देशिका:** UP Mandi Parishad से मंडल (division), जनपद, मण्डी, मण्डी ग्रेड, सचिव का नाम और सी.यू.जी नंबर।
- **📊 राज्य-स्तरीय संदर्भ भाव:** UP Krishi Vipran ticker स्पष्ट रूप से *state-level benchmark* के रूप में लेबल—किसी एक मंडी का भाव नहीं।
- **🛰️ Government Source Monitor + Official Portal cards:** हर सरकारी portal की live status, record count और सीधा link।
- **📊 Google Sheet / Excel ऑटो-सिंक:** एक लिंक अपनी शीट में लगाइए और भाव अपने आप अपडेट होते रहेंगे—कोई copy-paste नहीं। पूरी गाइड: [SETUP_SHEETS.md](SETUP_SHEETS.md)।
- **🔄 दिन में 4 बार auto-update:** 06:30, 12:30, 16:30 और 20:30 IST। Source failure पर last verified snapshot रखा जाता है—random data नहीं बनता।

---

## 🛠️ फ़ाइल संरचना (Project Structure)

```bash
├── index.html                  # मुख्य डैशबोर्ड (HTML + Tailwind + Chart.js)
├── admin.html                  # Admin panel (read-only: भाव देखें + official sync trigger)
├── manifest.json               # PWA कॉन्फ़िगरेशन (फ़ोन इंस्टॉल के लिए)
├── sw.js                       # सर्विस वर्कर (ऑफ़लाइन कैशिंग के लिए)
├── update_data.py              # Official multi-source data pipeline (no simulation)
├── export_sheets.py            # JSON snapshots → Google Sheets/Excel के लिए CSV feeds
├── data/
│   ├── latest.json             # 2-source gate पास UP verified prices
│   ├── source_prices.json      # हर official feed के अलग single-source prices
│   ├── state_prices.json       # State/district/mandi price summary
│   ├── mandis.json             # Mandi directory and available contacts
│   ├── auction.json            # Authorised e-NAM lot snapshot/status
│   ├── laws.json               # Act/rules section index and official links
│   ├── benchmarks.json         # State benchmark, Mandi Parishad directory, portals
│   ├── sources.json            # Portal health and refresh metadata
│   └── sheets/                 # ऑटो-अपडेट CSV feeds (Google Sheets / Excel के लिए)
│       ├── mandi_prices.csv    # सत्यापित मंडी भाव
│       ├── source_prices.csv   # स्रोत-वार single-source भाव
│       ├── state_prices.csv    # राज्य-वार सारांश
│       ├── mandi_directory.csv # मंडी निर्देशिका + सचिव/CUG
│       ├── price_history.csv   # भाव इतिहास (long format)
│       ├── source_status.csv   # सरकारी पोर्टल की स्थिति
│       ├── update_status.csv   # अंतिम अपडेट समय और गिनती
│       └── index.json          # सभी feeds की सूची + तैयार formula
├── scripts/
│   └── google_apps_script.gs   # Google Sheets auto-sync script (7 tabs, timed trigger)
├── SETUP_SHEETS.md             # शीट/Excel जोड़ने की पूरी गाइड
├── deploy.sh                   # GitHub Pages पर वन-क्लिक डिप्लॉय करने की स्क्रिप्ट
├── images/
│   ├── icon-512.png            # 512px ऐप आइकन
│   └── icon-192.png            # 192px ऐप आइकन
└── .github/
    └── workflows/
        └── update.yml          # दिन में 4 बार official feeds refresh करने का Action
```

---

## 🚀 स्थानीय सेटअप और चलाना (Local Setup & Run)

1. **क्लोन या डाउनलोड करें और फ़ोल्डर में जाएं:**
   ```bash
   cd mandi
   ```

2. **डेटा अपडेट करें (Run python updater):**
   ```bash
   python3 update_data.py
   ```

3. **स्थानीय static server चलाएं:**
   ```bash
   python3 -m http.server 8000
   ```
   फिर `http://localhost:8000` खोलें। Data fetch और PWA service worker के लिए `index.html` को `file://` से सीधे न खोलें।

### API/Docker मोड

```bash
cp .env.example .env
# .env में अपना JWT_SECRET और मजबूत ADMIN_PASSWORD भरें
docker compose up --build
```

`JWT_SECRET` बनाने के लिए `openssl rand -hex 32` का उपयोग कर सकते हैं। असली secret, password या access token को कभी commit न करें।

---

## 🌐 GitHub Pages पर लाइव डिप्लॉय करें (Deploy to GitHub Pages)

सुरक्षित deploy के लिए [GitHub CLI](https://cli.github.com/) install और authenticate करें:

```bash
gh auth login
bash deploy.sh
```

### यह स्क्रिप्ट क्या करेगी?
1. आपके local folder में Git repository तैयार करेगी।
2. बदलाव commit करेगी।
3. आपके authenticated GitHub account में repository बनाएगी या मौजूदा repository उपयोग करेगी।
4. GitHub Pages और Actions permissions चालू करेगी।

यह script कभी Personal Access Token नहीं मांगती और credential को Git remote URL में store नहीं करती।

---

## 📊 Google Sheet / Excel में ऑटो-अपडेट भाव

एक बार लिंक जोड़िए — भाव **दिन में 4 बार** (06:30, 12:30, 16:30, 20:30 IST) अपने आप अपडेट होते रहेंगे।

**Google Sheets** — नई शीट के cell **A1** में यह चिपकाएँ:

```
=IMPORTDATA("https://abhishekagrahari307-max.github.io/mandi/data/sheets/mandi_prices.csv")
```

**Excel** — `Data → From Web` में ऊपर वाला URL डालें → `Load` → फिर `Query Properties` में
*"Refresh every 60 minutes"* और *"Refresh data when opening the file"* पर ✅ लगाएँ।

उपलब्ध feeds: `mandi_prices`, `source_prices`, `state_prices`, `mandi_directory`,
`price_history`, `source_status`, `update_status` — सूची `data/sheets/index.json` में।

सातों तालिकाएँ अलग-अलग tab में और अपनी मर्ज़ी के समय पर चाहिए? `scripts/google_apps_script.gs`
इस्तेमाल करें। पूरी step-by-step गाइड: **[SETUP_SHEETS.md](SETUP_SHEETS.md)**

> ⚠️ **एक बार का ज़रूरी step:** `.github/workflows/update.yml` की `git add --` सूची में
> `data/sheets` जोड़ें, वरना scheduled refresh नई CSVs commit नहीं करेगा और शीट में भाव
> पुराने दिखते रहेंगे। विवरण [SETUP_SHEETS.md](SETUP_SHEETS.md) में।

> ये CSVs `update_data.py` हर refresh पर खुद बनाता है (`export_sheets.py` के ज़रिए)।
> हर cell सरकारी snapshot से आती है; कोई भाव बनाया नहीं जाता।
> `=`, `+`, `-`, `@` से शुरू होने वाली हर value को apostrophe लगाकर निष्क्रिय किया जाता है ताकि
> Excel/Sheets उसे formula की तरह न चलाएँ (CSV injection से बचाव)।

FastAPI सर्वर चलाने पर वही तालिकाएँ live भी मिलती हैं:

```
GET /api/v2/sheets                    # सभी feeds + तैयार formula
GET /api/v2/sheets/mandi_prices.csv   # कोई एक feed, CSV में
```

---

## ⚙️ आधिकारिक डेटा एकीकरण (Real data from Govt of India)

### 🔑 भाव नहीं दिख रहे? सबसे पहले यह करें — DATA_GOV_IN_API_KEY सेट करें

> 📄 **विस्तृत step-by-step गाइड (screenshots-जैसे निर्देश, troubleshooting table
> और सुरक्षा नियम के साथ): [SETUP_API_KEY.md](SETUP_API_KEY.md)**

Dashboard पर भाव न दिखने का **सबसे आम कारण** यही है कि `DATA_GOV_IN_API_KEY`
configure नहीं है। यह key **मुफ़्त** है। पूरा तरीका:

**चरण 1 — API key लें (5 मिनट, मुफ़्त)**
1. [https://data.gov.in](https://data.gov.in/) खोलें → ऊपर दाईं ओर **Sign Up / Register** पर क्लिक करें।
2. नाम, email और mobile भरकर account बनाएं और email/OTP से verify करें।
3. Login करने के बाद ऊपर दाईं ओर अपने **profile / My Account** में जाएं।
4. **APIs** या **My API Key** section खोलें — वहाँ एक लंबी key दिखेगी
   (उदाहरण: `579b464db66ec23bdd0000018...`)। उसे **Copy** कर लें।

**चरण 2 — key को GitHub repository secret में डालें**
1. अपनी GitHub repository खोलें → **Settings** tab।
2. बाएँ menu में **Secrets and variables** → **Actions** पर क्लिक करें।
3. हरे बटन **New repository secret** पर क्लिक करें।
4. भरें:
   - **Name:** `DATA_GOV_IN_API_KEY`  ← बिल्कुल यही spelling, capital letters में
   - **Secret:** चरण 1 में copy की हुई key paste करें
5. **Add secret** दबाएं।

> ⚠️ Key को कभी `README`, code, screenshot या chat में paste न करें — केवल
> GitHub Secret में रखें। Secret डालने के बाद वह दोबारा दिखता नहीं, केवल बदला जा सकता है।

**चरण 3 — तुरंत चलाकर देखें**
1. repository के **Actions** tab में जाएं।
2. बाईं ओर **Multi-Daily Mandi Price Update** workflow चुनें।
3. दाईं ओर **Run workflow** → फिर से **Run workflow** दबाएं।
4. Run हरा (✓) होने पर dashboard refresh करें — भाव आ जाने चाहिए।

**चरण 4 — जाँचें कि key काम कर रही है**
Dashboard के **"राज्य-वार भाव"** tab में नीचे **Government Source Monitor** देखें:
- `data.gov.in` की status **`ok`** होनी चाहिए।
- अगर अब भी `error: DATA_GOV_IN_API_KEY is not configured` दिखे तो secret का
  नाम गलत है (spelling/spacing जाँचें)।
- अगर `error: 401/403` दिखे तो key गलत या expire है — data.gov.in से नई लें।

इसके बाद dashboard दिन में 4 बार (06:30, 12:30, 16:30, 20:30 IST) official
OGD/AGMARKNET rates refresh करेगा। Key न होने या portal failure पर updater
**कोई random/simulated rate नहीं बनाता**; UI last verified snapshot या स्पष्ट
unavailable/unverified status दिखाता है।

### 2-source publication gate (कड़ा नियम)

**कोई भी मंडी भाव मुख्य सत्यापित तालिका में तभी प्रकाशित होता है जब कम से कम 2 configured
सरकारी price feeds एक ही market + commodity + date + modal price बताएं**
(`update_data.select_publishable_records`, `MIN_PRICE_SOURCE_MATCHES = 2`)।
भावों का औसत, अनुमान या interpolation कभी नहीं बनाया जाता — प्रकाशित भाव वही
संख्या है जो दोनों feeds ने बताई।

> **यह पहले 3 क्यों था और अब 2 क्यों है?** configured चार feeds में से केवल दो ही
> आम जनता को मिल सकते हैं: `data.gov.in` (मुफ़्त API key) और AGMARKNET (public
> report)। बाकी दो — e-NAM और UP e-Mandi trade feeds — केवल उन्हीं integrators को
> मिलते हैं जिन्हें संबंधित सरकारी portal ने authorise किया हो। इसलिए 3 का नियम
> व्यवहार में **हर भाव को हमेशा के लिए रोक देता था**, चाहे दोनों public feeds बिल्कुल
> एक जैसा भाव बताएं। दो स्वतंत्र सरकारी feeds का exact match अब भी असली
> cross-verification है।

**एकल-स्रोत (single-source) भाव:** अगर किसी भाव को केवल 1 feed ने बताया है तो वह
मुख्य verified तालिका में नहीं जाता, लेकिन dashboard उसे छिपाता भी नहीं। ऐसा भाव
**`⚠ 1 स्रोत — cross-verified नहीं`** badge और उस सरकारी feed के नाम के साथ दिखाया
जाता है, ताकि किसान/व्यापारी उसे कभी सत्यापित भाव न समझें। सौदे से पहले संबंधित
मंडी समिति से पुष्टि करने की सलाह UI में दी जाती है।

Pipeline इन सरकारी sources को अलग-अलग monitor करता है:

1. `data.gov.in` OGD API
2. AGMARKNET public report (`https://agmarknet.gov.in/home` portal health अलग से जाँची जाती है)
3. authorised e-NAM trade feed (`ENAM_TRADE_FEED_URL`, `ENAM_TRADE_API_KEY`)
4. authorised UP e-Mandi trade feed (`UP_EMANDI_TRADE_FEED_URL`, `UP_EMANDI_TRADE_API_KEY`)

इन चारों के अपने reported records `data/source_prices.json` में **अलग-अलग** रखे और dashboard
पर source label के साथ दिखाए जाते हैं। इनमें averaging, merging या missing भाव का अनुमान नहीं
लगाया जाता। ये single-source observations हैं; 2-source exact-match gate पास records ही
`data/latest.json` की सत्यापित मुख्य तालिका में जाते हैं। Feed की नई जाँच fail होने पर उसका आखिरी
official snapshot `cached` label के साथ रह सकता है।

तीसरा और चौथा feed public APIs नहीं हैं। इनके URLs/keys संबंधित सरकारी portal द्वारा approved
integrator को मिलने के बाद GitHub Actions secrets में जोड़ें; chat या repository में credentials
न लिखें। जब तक 2 feeds configured नहीं होते, dashboard "insufficient_sources" status दिखाता है
और मुख्य तालिका में कोई भाव प्रकाशित नहीं करता (single-source भाव लेबल के साथ अलग दिखते हैं)।

`.github/workflows/update.yml` इन सभी optional secrets (`ENAM_TRADE_*`, `UP_EMANDI_TRADE_*`,
`ENAM_AUCTION_*`, `DATA_GOV_RESOURCE_ID`) को updater तक पास करता है। जो secret set नहीं है वह
खाली रहता है और उसका feed `not_configured` के रूप में Government Source Monitor में दिखता है—
कोई fallback data नहीं बनता। हर run में updater `data/latest.json`, `data/source_prices.json`,
`data/history.json`, `data/state_prices.json`, `data/mandis.json`, `data/auction.json`,
`data/benchmarks.json` और `data/sources.json` commit करता है (simulated `data/weather.json` हटा दिया गया है)।

### मण्डी परिषद निर्देशिका (division, district, mandi, grade, secretary, CUG)

`https://dashboard.mandiprojects.in/MandiDetails.aspx` से हर अधिसूचित मण्डी की आधिकारिक पंक्ति
पढ़ी जाती है: **क्षेत्र (division), जिला, मण्डी नाम, मण्डी ग्रेड, सचिव का नाम और सी.यू.जी नंबर।**
यह `data/benchmarks.json` और `data/mandis.json` दोनों में जाती है, और sidebar/detail modal में
दिखती है। Portal पर `--` लिखा हो तो field खाली रहता है—कोई नकली नंबर नहीं भरा जाता।

### राज्य-स्तरीय संदर्भ भाव (state benchmark, मंडी भाव नहीं)

`https://www.upkrishivipran.in/Default.aspx` का official ticker पढ़ा जाता है और
`scope: "state_benchmark"`, `is_mandi_rate: false` के साथ store होता है। UI इसे अलग indigo
कार्ड में **"State-level benchmark — not an individual mandi rate"** लेबल के साथ दिखाता है।
यह कभी मंडी-वार तालिका, state summary या 2-source gate में नहीं मिलाया जाता।

### e-NAM live lots

Public e-NAM pages aggregate trade data देते हैं, लेकिन authenticated lot/bid feed public API नहीं है। यदि e-NAM/SFAC से अधिकृत integration feed मिला हो तो ये repository secrets जोड़ें:

- `ENAM_AUCTION_FEED_URL`
- `ENAM_AUCTION_API_KEY`

Feed JSON में `lot_number`, `district`, `mandi`, `commodity` और lot details होने चाहिए। इनके बिना auction tab official e-NAM link और “feed unavailable” status दिखाता है—नकली auction नहीं। Username/password को secret या scraper में न डालें।

### Official sources

1. [AGMARKNET](https://agmarknet.gov.in/home) — national mandi price portal.
2. Open Government Data (`data.gov.in`) — official price API built from AGMARKNET.
3. [UP Mandi Parishad directory](https://dashboard.mandiprojects.in/MandiDetails.aspx) — division, district, mandi, grade, secretary, CUG.
4. [UP Krishi Vipran](https://www.upkrishivipran.in/Default.aspx) — state-level benchmark ticker only.
5. UP e-Mandi contact directory — available mandi contacts and central helpdesk.
6. e-NAM — authorised auction lot feed and official bidding portal.
7. India Code / UP Mandi Parishad — Act, Rules and sections.

ये सभी `data/benchmarks.json` के `official_portals` में हैं और dashboard पर **Official Portals**
कार्ड तथा **Government Source Monitor** में live status के साथ दिखते हैं।

### एडमिन पैनल read-only क्यों है?

`admin.html` में भाव को हाथ से जोड़ने/बदलने/हटाने का कोई विकल्प नहीं है, क्योंकि
`app.py` इन तीनों पर **HTTP 405** लौटाता है (`POST`/`PUT`/`DELETE /api/v2/rates`)।
पहले पैनल में एक Add/Edit modal मौजूद था जो कभी save कर ही नहीं सकता था — वह dead
UI हटा दी गई है। भाव केवल सत्यापित सरकारी feeds से `update_data.py` के ज़रिए आते हैं।
पैनल से आप भाव **देख** सकते हैं और **Official Data Sync** चला सकते हैं।

### कोई simulated data नहीं

Repository में price, arrival, weather, auction lot, bid, prediction या alert-success का कोई
random/mock generator नहीं है। यह `tests/test_data_integrity.py` में enforce किया गया है
(`test_no_module_generates_random_values`). Source fail होने पर UI last verified snapshot या
स्पष्ट unavailable status दिखाता है।

---

Developed with ❤️ for farmers and traders of Uttar Pradesh.
*Vijay Kumar Traders, Kanpur Galla Mandi.*
