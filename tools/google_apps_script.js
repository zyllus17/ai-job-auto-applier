/**
 * AI Job Search - Google Sheets Webhook Script
 *
 * HOW TO SET UP (Takes 60 seconds):
 * 1. Create a new Google Sheet (e.g. "AI Job Search Tracker").
 * 2. In the top menu, go to: Extensions > Apps Script.
 * 3. Delete any code in the editor and paste THIS ENTIRE FILE.
 * 4. Click "Deploy" (blue button, top right) > "New deployment".
 * 5. Click the gear icon next to "Select type" > choose "Web app".
 * 6. Under "Execute as", select "Me".
 * 7. Under "Who has access", select "Anyone". (Allows Antigravity on your laptop to post data).
 * 8. Click "Deploy", authorize permissions when prompted, and COPY the Web App URL.
 * 9. Set the URL in Antigravity or in tools/google_sheets_sync.py!
 */

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    
    // Determine the tab name: default to today's date YYYY-MM-DD or provided date
    const dateStr = data.date || Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd");
    
    let sheet = ss.getSheetByName(dateStr);
    if (!sheet) {
      sheet = ss.insertSheet(dateStr);
      
      // Setup Header Row
      const headers = [
        "Timestamp",
        "Company",
        "Job Title",
        "Fit Score",
        "Status",
        "Missing High-Demand Skill",
        "Suggested 1-2 Hr Demo Project",
        "Location / Workplace",
        "Job URL",
        "Notes"
      ];
      
      sheet.appendRow(headers);
      const headerRange = sheet.getRange(1, 1, 1, headers.length);
      headerRange.setFontWeight("bold");
      headerRange.setBackground("#1a73e8");
      headerRange.setFontColor("#ffffff");
      sheet.setFrozenRows(1);
    }
    
    const rows = data.rows || [data];
    let addedCount = 0;
    
    rows.forEach(function(item) {
      sheet.appendRow([
        item.timestamp || Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm:ss"),
        item.company || "",
        item.title || "",
        item.fitScore || "",
        item.status || "Evaluated",
        item.missingSkill || "None",
        item.suggestedProject || "N/A",
        item.location || item.workplace || "Remote",
        item.url || "",
        item.notes || ""
      ]);
      addedCount++;
    });
    
    // Auto-fit columns
    for (let i = 1; i <= 10; i++) {
      sheet.autoResizeColumn(i);
    }
    
    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      rowsAdded: addedCount,
      tab: dateStr
    })).setMimeType(ContentService.MimeType.JSON);
    
  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({
    status: "online",
    service: "AI Job Search Google Sheets Sync Webhook",
    time: new Date().toISOString()
  })).setMimeType(ContentService.MimeType.JSON);
}
