# All Government Website Links Used in UP Mandi Dashboard
# यूपी मंडी डैशबोर्ड में उपयोग होने वाले सभी सरकारी वेबसाइट लिंक

This file lists every official government portal, API, and document link used in code, data generation, and UI.

## 1) Price Feeds - मुख्य भाव स्रोत (Mukhya Bhav Srot)

| ID | Name (EN) | Name (HI) | URL | Used In |
|----|-----------|-----------|-----|---------|
| data.gov.in | Open Government Data Platform | ओपन गवर्नमेंट डेटा | https://data.gov.in/ | `update_data.py` DATA_GOV_API, `OFFICIAL_PORTALS`, UI portal card |
| data.gov.in API | OGD Price API Resource | मूल्य API | https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070 and https://data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070 | `DATA_GOV_API`, `source_prices.json`, dashboard source-wise cards |
| AGMARKNET Home | Agricultural Marketing Info Network | कृषि विपणन सूचना नेटवर्क | https://agmarknet.gov.in/home | `AGMARKNET_HOME_URL`, portal health check, `OFFICIAL_PORTALS` |
| AGMARKNET Report | UP Price Report Table | यूपी मूल्य रिपोर्ट | https://agmarknet.gov.in/SearchCmmMkt.aspx?Tx_Commodity=0&Tx_State=UP&Tx_District=0&Tx_Market=0&Tx_Trend=0 and https://agmarknet.gov.in/SearchCmmMkt.aspx?Tx_Commodity=0&Tx_State=UP | `AGMARKNET_URL`, `fetch_agmarknet_up()` scraping for 2-source verification |

## 2) Mandi Directory & Contacts - मंडी निर्देशिका

| Name | URL | Purpose |
|------|-----|---------|
| UP Mandi Parishad Directory | https://dashboard.mandiprojects.in/MandiDetails.aspx | Division, District, Mandi, Grade, Secretary, CUG - parsed for `mandis.json` & `benchmarks.json` |
| UP Mandi Parishad Home | https://dashboard.mandiprojects.in/Home.aspx | Home check |
| UP e-Mandi Main Portal | https://emandi.up.gov.in/ | Mandi contact directory, gate-pass |
| UP e-Mandi Contact Us | https://emandi.up.gov.in/MandiHome/Contactus | Contact table parser `fetch_mandi_contacts()` |
| UP e-Mandi Training Mirror | https://www.emanditraining.in/MandiHome/Contactus | Fallback contact source |
| UP Mandi Parishad Official (old domain) | http://upmandiparishad.upsdc.gov.in and https://dashboard.mandiprojects.in/MandiDetails.aspx | Basti report portal cross-check |

## 3) State Benchmark - राज्य स्तरीय संदर्भ भाव

| Name | URL | Note |
|------|-----|------|
| UP Krishi Vipran Official Ticker | https://www.upkrishivipran.in/Default.aspx | STATE-LEVEL benchmark only, NOT individual mandi rate. Used in `benchmarks.json` |

## 4) e-NAM Auction - नीलामी

| Name | URL | Note |
|------|-----|------|
| e-NAM Official Portal | https://www.enam.gov.in/web/ | Official bidding - no simulated lots. Linked in UI "e-NAM पर Login / Bid करें" |
| e-NAM Trade Dashboard | https://enam.gov.in/web/dashboard/trade-data | Trade data verification link |

## 5) FCA / FCI - All India Average (Basti Division Cross-Check)

| Name | URL |
|------|-----|
| FCA Info Web | https://fcainfoweb.nic.in/ |
| FCI Main | https://fci.gov.in |

These two give All-India average retail/wholesale, NOT district-wise. Used in Basti Division portal cross-check.

## 6) Laws & Rules - अधिनियम और नियमावली

| Document | URL |
|----------|-----|
| U.P. Krishi Utpadan Mandi Adhiniyam 1964 (India Code) | https://www.indiacode.nic.in/bitstream/123456789/15730/1/english25of1964.pdf |
| U.P. Krishi Utpadan Mandi Niyamawali 1965 (India Code) | https://upload.indiacode.nic.in/showfile?actid=AC_UP_88_1449_00001_00001_1606284687214&filename=mandi_niyamwali_1965_english.pdf&type=rule |
| Mandi Projects Niyamawali Home | http://mandiprojects.in/NIPL/Niyamawali/Home.aspx |
| UP e-Mandi Licence Conditions | https://emandi.up.gov.in/application/license_reg_points |

## 7) Where Links Appear in Code

- `update_data.py`: `OFFICIAL_PORTALS` list, `AGMARKNET_HOME_URL`, `AGMARKNET_URL`, `MANDI_PARISHAD_DIRECTORY_URL`, `UP_KRISHI_VIPRAN_URL`, `ENAM_PORTAL_URL`, `ENAM_TRADE_URL`, `EMANDI_CONTACT_URLS`, `DATA_GOV_API`
- `data/benchmarks.json` / `data/sources.json`: `official_portals` array stores same URLs for UI
- `index.html`: `Official Portals` card, `Government Source Monitor`, Basti Division `portal_cross_check`, footer links, PDF sources
- `admin.html`: links via same data
- `app.py`: serves `/data/*.json` and mounts `/data` static
- `.env.example`: documents optional authorised feed URLs
- `README.md` & `SETUP_API_KEY.md`: documentation links to data.gov.in signup

## 8) Quick Copy List (All Unique gov domains)

```
https://agmarknet.gov.in/home
https://agmarknet.gov.in/SearchCmmMkt.aspx?Tx_Commodity=0&Tx_State=UP&Tx_District=0&Tx_Market=0&Tx_Trend=0
https://data.gov.in/
https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070
https://data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070
https://dashboard.mandiprojects.in/MandiDetails.aspx
https://dashboard.mandiprojects.in/Home.aspx
https://emandi.up.gov.in/
https://emandi.up.gov.in/MandiHome/Contactus
https://www.emanditraining.in/MandiHome/Contactus
https://www.upkrishivipran.in/Default.aspx
https://www.enam.gov.in/web/
https://enam.gov.in/web/dashboard/trade-data
https://fcainfoweb.nic.in/
https://fci.gov.in
https://www.indiacode.nic.in/bitstream/123456789/15730/1/english25of1964.pdf
https://upload.indiacode.nic.in/showfile?actid=AC_UP_88_1449_00001_00001_1606284687214&filename=mandi_niyamwali_1965_english.pdf&type=rule
http://mandiprojects.in/NIPL/Niyamawali/Home.aspx
https://emandi.up.gov.in/application/license_reg_points
```
