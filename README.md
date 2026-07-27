# 🌾 उत्तर प्रदेश लाइव मंडी भाव — UP Mandi Dashboard

एक आधुनिक, सुंदर, तेज और मोबाइल-फ्रेंडली (PWA) वेब एप्लिकेशन जो उत्तर प्रदेश की सभी बड़ी मंडियों के दैनिक कृषि भाव (गेहूं, धान, आलू, प्याज, टमाटर, आदि) को प्रदर्शित करता है।

यह प्रोजेक्ट **Vijay Kumar Traders** की डिजिटल सेवा के रूप में डिज़ाइन किया गया है।

---

## ✨ मुख्य विशेषताएं (Key Features)

- **🌐 पूर्णतः द्विभाषी (Bilingual):** एक क्लिक में हिन्दी और English के बीच बदलें।
- **📱 PWA इंस्टॉल करें (Add to Home Screen):** इसे फोन में इंस्टॉल करके बिना इंटरनेट (Offline Mode) के भी पुराने भाव देख सकते हैं।
- **🧮 मंडी बिल कैलकुलेटर (Interactive Calculator):** कुल वजन, भाव, आढ़त कमीशन, मजदूरी/पल्लेदारी, मंडी टैक्स और भाड़ा घटाकर किसान/व्यापारी का शुद्ध भुगतान (Net Payout) सेकंडों में निकालें।
- **📈 सत्यापित मूल्य ग्राफ (Verified Price Trends):** सफल सरकारी snapshots से बने वास्तविक ऐतिहासिक भाव देखें।
- **🏛️ पूरी मंडी निर्देशिका:** मंडी, जिला, जिंस, भाव सीमा, उपलब्ध स्थानीय अधिकारी संपर्क, केंद्रीय helpdesk और official links।
- **⚖️ अधिनियम और नियमावली:** U.P. Krishi Utpadan Mandi Adhiniyam 1964, Niyamawali 1965, अध्याय और धारा-सूची के official India Code links।
- **🔨 e-NAM नीलामी:** अधिकृत feed मिलने पर जिला एवं lot-wise read-only live snapshot; वास्तविक bid केवल authenticated e-NAM portal पर। कोई simulated lot/bid नहीं।
- **🗺️ राज्य-वार भाव:** data.gov.in/AGMARKNET records से राज्य, जिला, मंडी और प्रमुख जिंस का सारांश।
- **🔄 दिन में 6 बार auto-update:** 00:30, 04:30, 08:30, 12:30, 16:30 और 20:30 IST। Source failure पर last verified snapshot रखा जाता है—random data नहीं बनता।

---

## 🛠️ फ़ाइल संरचना (Project Structure)

```bash
├── index.html                  # मुख्य डैशबोर्ड (HTML + Tailwind + Chart.js)
├── manifest.json               # PWA कॉन्फ़िगरेशन (फ़ोन इंस्टॉल के लिए)
├── sw.js                       # सर्विस वर्कर (ऑफ़लाइन कैशिंग के लिए)
├── update_data.py              # Official multi-source data pipeline (no simulation)
├── data/
│   ├── latest.json             # UP official/cached verified prices
│   ├── state_prices.json       # State/district/mandi price summary
│   ├── mandis.json             # Mandi directory and available contacts
│   ├── auction.json            # Authorised e-NAM lot snapshot/status
│   ├── laws.json               # Act/rules section index and official links
│   └── sources.json            # Portal health and refresh metadata
├── deploy.sh                   # GitHub Pages पर वन-क्लिक डिप्लॉय करने की स्क्रिप्ट
├── images/
│   ├── icon-512.png            # 512px ऐप आइकन
│   └── icon-192.png            # 192px ऐप आइकन
└── .github/
    └── workflows/
        └── update.yml          # दिन में 6 बार official feeds refresh करने का Action
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
4. इसके बाद dashboard दिन में 6 बार official OGD/AGMARKNET rates refresh करेगा। Key न होने या portal failure पर updater **कोई random/simulated rate नहीं बनाता**; UI last verified snapshot या स्पष्ट unavailable/unverified status दिखाता है।

### 3/4-source price verification

Pipeline इन सरकारी sources को अलग-अलग monitor करता है और market + commodity + date + modal price match होने पर ही record को cross-verified मानता है:

1. `data.gov.in` OGD API
2. AGMARKNET public report
3. authorised e-NAM trade feed (`ENAM_TRADE_FEED_URL`, `ENAM_TRADE_API_KEY`)
4. authorised UP e-Mandi trade feed (`UP_EMANDI_TRADE_FEED_URL`, `UP_EMANDI_TRADE_API_KEY`)

तीसरे और चौथे feed public APIs नहीं हैं। इनके URLs/keys संबंधित सरकारी portal द्वारा approved integrator को मिलने के बाद GitHub Actions secrets में जोड़ें; chat या repository में credentials न लिखें। UI connected source count और 3+ source से match हुए records अलग दिखाती है।

### e-NAM live lots

Public e-NAM pages aggregate trade data देते हैं, लेकिन authenticated lot/bid feed public API नहीं है। यदि e-NAM/SFAC से अधिकृत integration feed मिला हो तो ये repository secrets जोड़ें:

- `ENAM_AUCTION_FEED_URL`
- `ENAM_AUCTION_API_KEY`

Feed JSON में `lot_number`, `district`, `mandi`, `commodity` और lot details होने चाहिए। इनके बिना auction tab official e-NAM link और “feed unavailable” status दिखाता है—नकली auction नहीं। Username/password को secret या scraper में न डालें।

### Official sources

1. Open Government Data (`data.gov.in`) / AGMARKNET — prices.
2. UP e-Mandi contact directory — available mandi contacts and central helpdesk.
3. e-NAM — authorised auction lot feed and official bidding portal.
4. India Code / UP Mandi Parishad — Act, Rules and sections.

---

Developed with ❤️ for farmers and traders of Uttar Pradesh.
*Vijay Kumar Traders, Kanpur Galla Mandi.*
