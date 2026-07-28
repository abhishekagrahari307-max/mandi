/**
 * UP Mandi Dashboard — Google Sheets auto-sync
 * यूपी मंडी डैशबोर्ड — गूगल शीट स्वतः-अपडेट स्क्रिप्ट
 *
 * यह script हर सरकारी CSV feed को अपनी अलग tab में लाती है और एक time-trigger
 * से अपने आप refresh करती रहती है। =IMPORTDATA से यह बेहतर है क्योंकि:
 *   • हर feed अपनी tab में जाता है (7 tabs एक साथ)
 *   • refresh का समय आप खुद तय करते हैं (Google का ~1 घंटा नहीं)
 *   • feed fail होने पर पुरानी sheet मिटती नहीं, बस एक note लिखा जाता है
 *
 * उपयोग / Setup:
 *   1. एक नई Google Sheet खोलें → Extensions → Apps Script
 *   2. सारा code वहाँ paste करें और Save करें
 *   3. Run → setUpMandiAutoSync (पहली बार permission माँगेगा, Allow करें)
 *   4. बस! अब sheet हर 4 घंटे में अपने आप update होगी।
 *
 * BASE_URL: अपनी deployment के हिसाब से बदलें।
 *   • GitHub Pages : https://<user>.github.io/mandi/data/sheets
 *   • FastAPI सर्वर : https://<your-server>/api/v2/sheets   (फ़ाइल नाम वही रहेंगे)
 */

var BASE_URL = 'https://abhishekagrahari307-max.github.io/mandi/data/sheets';

/** हर tab और उसकी CSV फ़ाइल। */
var FEEDS = [
  { tab: 'Mandi Bhav',       file: 'mandi_prices.csv'    },
  { tab: 'Source Wise Bhav', file: 'source_prices.csv'   },
  { tab: 'State Summary',    file: 'state_prices.csv'    },
  { tab: 'Mandi Directory',  file: 'mandi_directory.csv' },
  { tab: 'Price History',    file: 'price_history.csv'   },
  { tab: 'Source Status',    file: 'source_status.csv'   },
  { tab: 'Update Status',    file: 'update_status.csv'   }
];

/** कितने घंटे में एक बार refresh हो (सरकारी feed दिन में 4 बार बदलता है)। */
var REFRESH_EVERY_HOURS = 4;

/**
 * एक बार चलाएँ: सारे tabs भरता है और auto-refresh trigger लगाता है।
 */
function setUpMandiAutoSync() {
  removeExistingTriggers_();
  ScriptApp.newTrigger('refreshMandiSheets')
    .timeBased()
    .everyHours(REFRESH_EVERY_HOURS)
    .create();
  refreshMandiSheets();
}

/**
 * हर feed को उसकी tab में दोबारा लिखता है। Trigger इसी को बुलाता है।
 */
function refreshMandiSheets() {
  var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  var stamp = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'dd-MM-yyyy HH:mm');

  FEEDS.forEach(function (feed) {
    var sheet = spreadsheet.getSheetByName(feed.tab) || spreadsheet.insertSheet(feed.tab);
    var rows = fetchCsvRows_(BASE_URL + '/' + feed.file);

    if (rows === null) {
      // Feed नहीं मिला — पुराना data मिटाना नहीं है, सिर्फ़ चेतावनी लिखें।
      sheet.getRange(1, 1).setNote('अंतिम प्रयास विफल: ' + stamp);
      return;
    }

    sheet.clearContents();
    sheet.clearNotes();
    if (rows.length === 0) {
      sheet.getRange(1, 1).setValue('इस समय कोई सरकारी record प्रकाशित नहीं है — ' + stamp);
      return;
    }

    var width = rows.reduce(function (max, row) { return Math.max(max, row.length); }, 0);
    var padded = rows.map(function (row) {
      var copy = row.slice();
      while (copy.length < width) { copy.push(''); }
      return copy;
    });

    sheet.getRange(1, 1, padded.length, width).setValues(padded);
    sheet.getRange(1, 1, 1, width).setFontWeight('bold');
    sheet.setFrozenRows(1);
    sheet.getRange(1, 1).setNote('अंतिम अपडेट: ' + stamp + ' IST');
  });
}

/**
 * CSV लाकर parse करता है। विफल होने पर null लौटाता है ताकि पुराना data बचा रहे।
 */
function fetchCsvRows_(url) {
  try {
    var response = UrlFetchApp.fetch(url + '?t=' + Date.now(), {
      muteHttpExceptions: true,
      followRedirects: true
    });
    if (response.getResponseCode() !== 200) { return null; }
    var text = response.getContentText('UTF-8').trim();
    if (!text) { return []; }
    return Utilities.parseCsv(text);
  } catch (error) {
    return null;
  }
}

/** पुराने trigger हटाता है ताकि setup दोबारा चलाने पर duplicate न बनें। */
function removeExistingTriggers_() {
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    if (trigger.getHandlerFunction() === 'refreshMandiSheets') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
}

/** Sheet में एक "मंडी भाव" menu जोड़ता है — मैनुअल refresh के लिए। */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('🌾 मंडी भाव')
    .addItem('अभी अपडेट करें (Refresh now)', 'refreshMandiSheets')
    .addItem('ऑटो-अपडेट चालू करें (Set up auto-sync)', 'setUpMandiAutoSync')
    .addToUi();
}
