# 📊 Google Sheet / Excel में ऑटो-अपडेट भाव

**एक बार जोड़िए — भाव अपने आप अपडेट होते रहेंगे।** कोई copy-paste नहीं, कोई manual download नहीं।

भाव दिन में **4 बार** अपडेट होते हैं: **06:30, 12:30, 16:30, 20:30 IST**।

---

## ⚠️ पहले यह एक line जोड़नी ज़रूरी है (सिर्फ़ एक बार)

CSV फ़ाइलें `update_data.py` हर refresh पर खुद बना देता है, लेकिन GitHub Action उन्हें
commit तभी करेगा जब उसकी file-list में `data/sheets` भी हो। **इसके बिना शीट में भाव
पुराने ही दिखते रहेंगे।**

`.github/workflows/update.yml` खोलिए और `git add --` वाली सूची के अंत में `data/sheets`
जोड़ दीजिए:

```yaml
          git add -- \
            data/latest.json \
            data/source_prices.json \
            data/history.json \
            data/state_prices.json \
            data/mandis.json \
            data/auction.json \
            data/benchmarks.json \
            data/sources.json \
            data/sheets            # ← यह line जोड़ें
```

> यह बदलाव agent नहीं कर सका क्योंकि GitHub App को workflow files बदलने की permission
> नहीं होती — इसे आपको खुद (या repo settings में `workflows` permission देकर) करना होगा।
> जब तक यह न हो, `tests/test_sheet_export.py` में एक test *skip* होकर याद दिलाता रहेगा।

---

## 🔗 आपके लिंक (CSV feeds)

हर तालिका का अपना लिंक है। जो चाहिए वही उठाइए:

| # | तालिका | फ़ाइल | लिंक |
|---|--------|-------|------|
| 1 | सत्यापित मंडी भाव | `mandi_prices.csv` | `https://abhishekagrahari307-max.github.io/mandi/data/sheets/mandi_prices.csv` |
| 2 | स्रोत-वार भाव (single-source) | `source_prices.csv` | `.../data/sheets/source_prices.csv` |
| 3 | राज्य-वार सारांश | `state_prices.csv` | `.../data/sheets/state_prices.csv` |
| 4 | मंडी निर्देशिका + सचिव/CUG | `mandi_directory.csv` | `.../data/sheets/mandi_directory.csv` |
| 5 | भाव इतिहास (graph के लिए) | `price_history.csv` | `.../data/sheets/price_history.csv` |
| 6 | सरकारी पोर्टल की स्थिति | `source_status.csv` | `.../data/sheets/source_status.csv` |
| 7 | अंतिम अपडेट जानकारी | `update_status.csv` | `.../data/sheets/update_status.csv` |

> सारे लिंक की सूची यहाँ भी मिलेगी: `data/sheets/index.json`
> डैशबोर्ड पर भी ये लिंक **"Google Sheet / Excel में ऑटो-अपडेट भाव"** बॉक्स में copy बटन के साथ मिलते हैं।

---

## 🟢 तरीका 1 — Google Sheets (सबसे आसान, 30 सेकंड)

1. [sheets.new](https://sheets.new) पर नई शीट खोलें
2. **cell A1** में यह चिपकाएँ और Enter दबाएँ:

```
=IMPORTDATA("https://abhishekagrahari307-max.github.io/mandi/data/sheets/mandi_prices.csv")
```

3. बस! पूरी तालिका अपने आप भर जाएगी।

**अपडेट कब होगा?** Google `IMPORTDATA` को लगभग **हर 1 घंटे** में और **हर बार शीट खोलने पर** दोबारा लाता है। आपको कुछ नहीं करना।

**एक ही शीट में कई तालिकाएँ?** नीचे नई tab बनाइए और उसके A1 में दूसरा लिंक डाल दीजिए।

---

## 🔵 तरीका 2 — Google Sheets + Apps Script (ज़्यादा control)

अगर आप चाहते हैं कि **सातों तालिकाएँ अलग-अलग tab में** आएँ और refresh का समय **आप तय करें**:

1. Google Sheet → **Extensions → Apps Script**
2. `scripts/google_apps_script.gs` का पूरा code वहाँ चिपकाएँ → Save
3. ऊपर से **`setUpMandiAutoSync`** चुनकर **Run** दबाएँ (पहली बार permission माँगेगा → Allow)
4. हो गया — अब हर 4 घंटे में सातों tab अपने आप भरेंगी

इसका फ़ायदा:
- सातों feed एक साथ, अपनी-अपनी tab में
- refresh हर 4 घंटे (आप `REFRESH_EVERY_HOURS` बदल सकते हैं)
- कोई feed fail हो तो **पुराना data मिटता नहीं**, बस एक note लग जाता है
- शीट में एक **"🌾 मंडी भाव"** menu भी आ जाता है — जब चाहें "अभी अपडेट करें" दबाइए

---

## 🟠 तरीका 3 — Microsoft Excel (Power Query)

Excel में formula से auto-refresh नहीं होता, इसलिए **Data → From Web** इस्तेमाल करें:

1. Excel खोलें → रिबन में **Data** → **From Web**
2. URL में यह चिपकाएँ:
   ```
   https://abhishekagrahari307-max.github.io/mandi/data/sheets/mandi_prices.csv
   ```
3. **OK** → **Load** दबाएँ

### अब auto-refresh चालू करें (ज़रूरी step)

4. **Data → Queries & Connections** → अपनी query पर **right-click** → **Properties**
5. दो box पर ✅ लगाएँ:
   - ☑️ **Refresh every `60` minutes**
   - ☑️ **Refresh data when opening the file**
6. **OK**

बस! अब जब भी Excel खुला रहेगा, हर घंटे नया भाव आ जाएगा — और file खोलते ही भी।

> **Advanced Editor** पसंद है? हर feed की तैयार Power Query (M) script `data/sheets/index.json` में `excel_power_query` field के अंदर मिल जाएगी।

---

## 🖥️ अगर आप FastAPI सर्वर चला रहे हैं

Server चलने पर वही तालिकाएँ live API से भी मिलती हैं (हमेशा ताज़ा, कोई cache नहीं):

```
GET /api/v2/sheets                    → सारी feeds की सूची + तैयार formula
GET /api/v2/sheets/mandi_prices.csv   → कोई भी एक feed, CSV में
```

उदाहरण:
```
=IMPORTDATA("https://your-server.com/api/v2/sheets/mandi_prices.csv")
```

---

## 📋 कॉलम की जानकारी

**`mandi_prices.csv`** (मुख्य तालिका):

| कॉलम | मतलब |
|------|------|
| `Date` | सरकारी feed में दर्ज आवक तिथि |
| `District` / `जिला` | जनपद (अंग्रेज़ी और हिन्दी) |
| `Mandi` | मंडी का नाम |
| `Commodity` / `जिंस` | फसल |
| `Variety`, `Grade` | किस्म और ग्रेड |
| `Min_Price`, `Modal_Price`, `Max_Price` | ₹ प्रति क्विंटल |
| `Verified_By` | किन-किन सरकारी feeds ने यही भाव बताया |
| `Source_Count` | कितने feeds ने मिलान किया (कम से कम 2) |
| `Updated_At_IST` | भाव कब प्रकाशित हुआ |

---

## ❓ अक्सर पूछे जाने वाले सवाल

**शीट खाली दिख रही है — क्यों?**
इसका मतलब उस समय किसी भी सरकारी feed से 2-source सत्यापित भाव नहीं मिला। यह प्रोजेक्ट **कभी नकली भाव नहीं भरता** — खाली तालिका का मतलब है "अभी सरकारी data उपलब्ध नहीं"। `update_status.csv` और `source_status.csv` खोलकर कारण देख सकते हैं।

**`#REF!` या `#ERROR!` आ रहा है?**
Google को लिंक तक पहुँचने दें — शीट में `File → Settings` देखें, या formula दोबारा Enter करें। लिंक `https://` से शुरू होना चाहिए।

**क्या भाव बदले जा सकते हैं / अपने हिसाब से जोड़ सकते हैं?**
`IMPORTDATA` वाली cells पर सीधे न लिखें (वे हर refresh पर मिट जाएँगी)। बगल के खाली कॉलम में अपना calculation लिखें, जैसे `=H2*0.94` (कमीशन घटाकर)।

**Excel में `+91-...` जैसे नंबर के आगे `'` क्यों दिखता है?**
सुरक्षा के लिए। `=`, `+`, `-`, `@` से शुरू होने वाली value को Excel/Sheets *formula* मान लेते हैं। इसलिए ऐसी हर सरकारी value के आगे एक apostrophe लगाया जाता है ताकि वह सिर्फ़ text रहे — यह एक जाना-माना CSV injection बचाव है।

---

## 🔒 डेटा नीति

- हर cell किसी **आधिकारिक सरकारी snapshot** से ली गई है
- कोई भाव, आवक, संपर्क या नीलामी **बनाई नहीं जाती**
- एक भाव तभी `mandi_prices.csv` में जाता है जब **कम से कम 2 सरकारी feeds** एक ही मंडी, जिंस, तिथि और modal price बताएँ
- सिर्फ़ एक feed वाले भाव अलग `source_prices.csv` में, साफ़ `single_source` label के साथ
- भाव कभी **औसत या मिलाए नहीं जाते**
