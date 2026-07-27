# 🔑 भाव चालू करें — DATA_GOV_IN_API_KEY सेटअप गाइड

> **एक लाइन में:** dashboard पर भाव इसलिए नहीं दिख रहे क्योंकि सरकारी price feed
> से जुड़ने वाली **मुफ़्त API key** अभी सेट नहीं है। नीचे दिए 4 चरण (कुल ~10 मिनट)
> पूरे करते ही भाव अपने-आप आने लगेंगे।

---

## ⚠️ पहले यह पढ़ें (सुरक्षा)

- API key एक **पासवर्ड जैसी** चीज़ है। इसे कभी भी किसी को चैट, WhatsApp,
  screenshot या email में न भेजें — **मुझे भी नहीं**।
- Key को केवल **GitHub Secret** में डालें। वहाँ डालने के बाद वह किसी को दिखती
  नहीं, केवल बदली जा सकती है।
- Key को कभी `README.md`, `update_data.py` या किसी भी code file में paste न करें।
  अगर गलती से ऐसा हो जाए तो data.gov.in से तुरंत नई key बनाएं (regenerate)।

---

## चरण 1 — data.gov.in से मुफ़्त API key लें (~5 मिनट)

1. ब्राउज़र में [https://data.gov.in](https://data.gov.in/) खोलें।
2. ऊपर दाईं ओर **Sign Up / Register** पर क्लिक करें।
3. अपना नाम, email और mobile number भरकर account बनाएं।
4. Email पर आए link या mobile पर आए OTP से account **verify** करें।
5. Login करें → ऊपर दाईं ओर अपने नाम/profile icon पर क्लिक करें।
6. **My Account** → **APIs** (या **My API Key**) section खोलें।
7. वहाँ एक लंबी key दिखेगी, कुछ ऐसी:
   ```
   579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b
   ```
8. उसे **Copy** कर लें।

> 💡 Key न मिले तो data.gov.in के **Contact / Help** page से support को लिखें;
> key सभी registered users को मुफ़्त मिलती है।

---

## चरण 2 — key को GitHub repository secret में डालें (~2 मिनट)

1. अपनी repository खोलें: `https://github.com/<आपका-username>/mandi`
2. ऊपर **Settings** tab पर क्लिक करें।
3. बाएँ menu में नीचे जाकर **Secrets and variables** → **Actions** चुनें।
4. हरे बटन **New repository secret** पर क्लिक करें।
5. दो field भरें:

   | Field | क्या भरें |
   |---|---|
   | **Name** | `DATA_GOV_IN_API_KEY` |
   | **Secret** | चरण 1 में copy की हुई key |

   > ⚠️ **Name बिल्कुल यही** होना चाहिए — पूरा CAPITAL letters में, बीच में
   > underscore `_`, कोई space नहीं। spelling में ज़रा-सी गलती होने पर key
   > काम नहीं करेगी।

6. **Add secret** दबाएं।

---

## चरण 3 — तुरंत चलाकर देखें (~2 मिनट)

1. repository में ऊपर **Actions** tab पर क्लिक करें।
2. बाईं ओर की list में **Multi-Daily Mandi Price Update** चुनें।
3. दाईं ओर **Run workflow** dropdown → फिर हरा **Run workflow** बटन दबाएं।
4. ~1-2 मिनट रुकें। Run के आगे हरा ✓ आना चाहिए।
5. अब अपना dashboard खोलें और page **refresh** करें (मोबाइल पर pull-to-refresh)।

---

## चरण 4 — जाँचें कि key सच में काम कर रही है

Dashboard खोलकर **"राज्य-वार भाव"** tab पर जाएं और नीचे
**Government Source Monitor** कार्ड देखें:

| आपको जो दिखे | मतलब | क्या करें |
|---|---|---|
| `data.gov.in` → **`ok`** | ✅ सब ठीक है | कुछ नहीं, भाव आ जाएंगे |
| `error: DATA_GOV_IN_API_KEY is not configured` | Secret का **नाम गलत** है | चरण 2 दोबारा करें, spelling जाँचें |
| `error: 401` या `403` | Key **गलत या expire** है | data.gov.in से नई key लेकर Secret update करें |
| `error: 429` | बहुत ज़्यादा requests | कुछ घंटे रुकें, अपने-आप ठीक हो जाएगा |
| `error: TLS/SSL...` | Portal अस्थायी रूप से down है | कुछ देर बाद अपने-आप retry होगा |

Header के ऊपर **भाव अपडेट समय** bar में भी अब असली समय दिखने लगेगा।

---

## ❓ Key डालने के बाद भी भाव नहीं दिख रहे?

यह **सामान्य** हो सकता है। Dashboard किसी भाव को मुख्य सत्यापित तालिका में तभी
दिखाता है जब **कम से कम 2 सरकारी feeds एक ही भाव** बताएं।

- अगर सिर्फ़ 1 feed ने भाव दिया है, तो वह भाव फिर भी दिखेगा — लेकिन
  **`⚠ 1 स्रोत — cross-verified नहीं`** badge के साथ। यह जान-बूझकर है, ताकि आप
  उसे सत्यापित भाव न समझें।
- अगर बिल्कुल कुछ नहीं दिख रहा, तो table के नीचे लिखा संदेश पढ़ें — वह असली
  कारण बताता है (feed नहीं जुड़ा / feeds का मिलान नहीं हुआ / filter लगा है)।

छुट्टी के दिन या रात में मंडियां बंद होने पर सरकारी portal भी नए भाव प्रकाशित
नहीं करता — ऐसे में पुराना verified snapshot दिखता रहेगा, जो सही व्यवहार है।

---

## 🧩 वैकल्पिक (Optional) secrets

ये केवल उन्हें चाहिए जिन्हें संबंधित सरकारी portal ने **authorised integrator**
बनाया हो। इनके बिना भी dashboard पूरी तरह काम करता है:

| Secret | किसके लिए |
|---|---|
| `ENAM_TRADE_FEED_URL`, `ENAM_TRADE_API_KEY` | e-NAM का अधिकृत trade feed |
| `UP_EMANDI_TRADE_FEED_URL`, `UP_EMANDI_TRADE_API_KEY` | UP e-Mandi trade feed |
| `ENAM_AUCTION_FEED_URL`, `ENAM_AUCTION_API_KEY` | e-NAM live नीलामी lots |
| `DATA_GOV_RESOURCE_ID` | data.gov.in का कोई दूसरा price resource |

इनका username/password कभी scraper या code में न डालें।

---

*अधिक जानकारी के लिए मुख्य [README.md](README.md) देखें।*
