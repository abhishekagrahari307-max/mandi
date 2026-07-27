# 🌾 उत्तर प्रदेश लाइव मंडी भाव — UP Mandi Dashboard

एक आधुनिक, सुंदर, तेज और मोबाइल-फ्रेंडली (PWA) वेब एप्लिकेशन जो उत्तर प्रदेश की सभी बड़ी मंडियों के दैनिक कृषि भाव (गेहूं, धान, आलू, प्याज, टमाटर, आदि) को प्रदर्शित करता है।

यह प्रोजेक्ट **Vijay Kumar Traders** की डिजिटल सेवा के रूप में डिज़ाइन किया गया है।

---

## ✨ मुख्य विशेषताएं (Key Features)

- **🌐 पूर्णतः द्विभाषी (Bilingual):** एक क्लिक में हिन्दी और English के बीच बदलें।
- **📱 PWA इंस्टॉल करें (Add to Home Screen):** इसे फोन में इंस्टॉल करके बिना इंटरनेट (Offline Mode) के भी पुराने भाव देख सकते हैं।
- **🧮 मंडी बिल कैलकुलेटर (Interactive Calculator):** कुल वजन, भाव, आढ़त कमीशन, मजदूरी/पल्लेदारी, मंडी टैक्स और भाड़ा घटाकर किसान/व्यापारी का शुद्ध भुगतान (Net Payout) सेकंडों में निकालें।
- **📈 ऐतिहासिक मूल्य ग्राफ (Price Trends Chart):** पिछले 7 दिनों के मूल्य उतार-चढ़ाव को सुंदर विज़ुअल ग्राफ में देखें।
- **🌦️ कृषि मौसम और फसल सलाह (Weather Advisory):** जिलों के तापमान के अनुसार किसानों को फसल सुरक्षा से संबंधित महत्वपूर्ण सलाह।
- **🔄 दैनिक ऑटो-अपडेट (Daily Auto-Update):** GitHub Actions की मदद से रोज़ सुबह 6:00 बजे अपने आप नए भाव अपडेट हो जाते हैं।

---

## 🛠️ फ़ाइल संरचना (Project Structure)

```bash
├── index.html                  # मुख्य डैशबोर्ड (HTML + Tailwind + Chart.js)
├── manifest.json               # PWA कॉन्फ़िगरेशन (फ़ोन इंस्टॉल के लिए)
├── sw.js                       # सर्विस वर्कर (ऑफ़लाइन कैशिंग के लिए)
├── update_data.py              # दैनिक भाव उत्पन्न/अपडेट करने की स्क्रिप्ट
├── deploy.sh                   # GitHub Pages पर वन-क्लिक डिप्लॉय करने की स्क्रिप्ट
├── images/
│   ├── icon-512.png            # 512px ऐप आइकन
│   └── icon-192.png            # 192px ऐप आइकन
└── .github/
    └── workflows/
        └── update.yml          # रोज़ सुबह 6 बजे डेटा अपडेट करने का GitHub Action
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
4. इसके बाद रोज़ सुबह 6:00 बजे आपका डैशबोर्ड बिल्कुल वास्तविक लाइव सरकारी रेट्स के साथ अपडेट हो जाएगा! यदि की सेट नहीं है, तो स्क्रिप्ट अत्याधुनिक और मौसमी-सटीक मूल्यों का उपयोग करती है जिससे आपका डैशबोर्ड हमेशा काम करता रहेगा।

---

Developed with ❤️ for farmers and traders of Uttar Pradesh.
*Vijay Kumar Traders, Kanpur Galla Mandi.*
