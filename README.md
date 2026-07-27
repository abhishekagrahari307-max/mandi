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
- **🏛️ पूरी मंडी निर्देशिका:** मंडी, जिला, जिंस, भाव सीमा, उपलब्ध स्थानीय अधिकारी संपर्क, केंद्रीय helpdesk और official links।
- **⚖️ अधिनियम और नियमावली:** U.P. Krishi Utpadan Mandi Adhiniyam 1964, Niyamawali 1965, अध्याय और धारा-सूची के official India Code links।
- **🔨 e-NAM नीलामी:** अधिकृत feed मिलने पर जिला एवं lot-wise read-only live snapshot; वास्तविक bid केवल authenticated e-NAM portal पर। कोई simulated lot/bid नहीं।
- **🗺️ राज्य-वार भाव:** केवल 3+ सरकारी feeds पर match हुए records से राज्य, जिला, मंडी और जिंस का सारांश।
- **🏢 मण्डी परिषद निर्देशिका:** UP Mandi Parishad से मंडल (division), जनपद, मण्डी, मण्डी ग्रेड, सचिव का नाम और सी.यू.जी नंबर।
- **📊 राज्य-स्तरीय संदर्भ भाव:** UP Krishi Vipran ticker स्पष्ट रूप से *state-level benchmark* के रूप में लेबल—किसी एक मंडी का भाव नहीं।
- **🛰️ Government Source Monitor + Official Portal cards:** हर सरकारी portal की live status, record count और सीधा link।
- **🔄 दिन में 4 बार auto-update:** 06:30, 12:30, 16:30 और 20:30 IST। Source failure पर last verified snapshot रखा जाता है—random data नहीं बनता।

---

## 🛠️ फ़ाइल संरचना (Project Structure)

```bash
├── index.html                  # मुख्य डैशबोर्ड (HTML + Tailwind + Chart.js)
├── manifest.json               # PWA कॉन्फ़िगरेशन (फ़ोन इंस्टॉल के लिए)
├── sw.js                       # सर्विस वर्कर (ऑफ़लाइन कैशिंग के लिए)
├── update_data.py              # Official multi-source data pipeline (no simulation)
├── data/
│   ├── latest.json             # 3-source gate पास UP verified prices
│   ├── source_prices.json      # हर official feed के अलग single-source prices
│   ├── state_prices.json       # State/district/mandi price summary
│   ├── mandis.json             # Mandi directory and available contacts
│   ├── auction.json            # Authorised e-NAM lot snapshot/status
│   ├── laws.json               # Act/rules section index and official links
│   ├── benchmarks.json         # State benchmark, Mandi Parishad directory, portals
│   └── sources.json            # Portal health and refresh metadata
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

## ⚙️ आधिकारिक डेटा एकीकरण (Real data from Govt of India)

यदि आप **data.gov.in** के वास्तविक रीयल-टाइम डेटा को जोड़ना चाहते हैं, तो:
1. [data.gov.in](https://data.gov.in/) पर साइन अप करें और अपनी **API Key** प्राप्त करें।
2. अपने GitHub रिपॉजिटरी की **Settings -> Secrets and variables -> Actions** में जाएं।
3. एक नया Secret बनाएं:
   - **Name:** `DATA_GOV_IN_API_KEY`
   - **Value:** *[आपकी API Key]*
4. इसके बाद dashboard दिन में 4 बार (06:30, 12:30, 16:30, 20:30 IST) official
   OGD/AGMARKNET rates refresh करेगा। Key न होने या portal failure पर updater **कोई random/simulated rate नहीं बनाता**; UI last verified snapshot या स्पष्ट unavailable/unverified status दिखाता है।

### 3-source publication gate (कड़ा नियम)

**कोई भी मंडी भाव तभी प्रकाशित होता है जब कम से कम 3 configured सरकारी price feeds एक ही
market + commodity + date + modal price बताएं।** 1 या 2 feeds के match पर record रोक दिया
जाता है—अनुमान या औसत नहीं बनाया जाता (`update_data.select_publishable_records`,
`MIN_PRICE_SOURCE_MATCHES = 3`).

Pipeline इन सरकारी sources को अलग-अलग monitor करता है:

1. `data.gov.in` OGD API
2. AGMARKNET public report (`https://agmarknet.gov.in/home` portal health अलग से जाँची जाती है)
3. authorised e-NAM trade feed (`ENAM_TRADE_FEED_URL`, `ENAM_TRADE_API_KEY`)
4. authorised UP e-Mandi trade feed (`UP_EMANDI_TRADE_FEED_URL`, `UP_EMANDI_TRADE_API_KEY`)

इन चारों के अपने reported records `data/source_prices.json` में **अलग-अलग** रखे और dashboard
पर source label के साथ दिखाए जाते हैं। इनमें averaging, merging या missing भाव का अनुमान नहीं
लगाया जाता। ये single-source observations हैं; 3-source exact-match gate पास records ही
`data/latest.json` की सत्यापित मुख्य तालिका में जाते हैं। Feed की नई जाँच fail होने पर उसका आखिरी
official snapshot `cached` label के साथ रह सकता है।

तीसरे और चौथे feed public APIs नहीं हैं। इनके URLs/keys संबंधित सरकारी portal द्वारा approved
integrator को मिलने के बाद GitHub Actions secrets में जोड़ें; chat या repository में credentials
न लिखें। जब तक 3 feeds configured नहीं होते, dashboard "insufficient_sources" status दिखाता है
और कोई भाव प्रकाशित नहीं करता।

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
यह कभी मंडी-वार तालिका, state summary या 3-source gate में नहीं मिलाया जाता।

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

### कोई simulated data नहीं

Repository में price, arrival, weather, auction lot, bid, prediction या alert-success का कोई
random/mock generator नहीं है। यह `tests/test_data_integrity.py` में enforce किया गया है
(`test_no_module_generates_random_values`). Source fail होने पर UI last verified snapshot या
स्पष्ट unavailable status दिखाता है।

---

Developed with ❤️ for farmers and traders of Uttar Pradesh.
*Vijay Kumar Traders, Kanpur Galla Mandi.*
