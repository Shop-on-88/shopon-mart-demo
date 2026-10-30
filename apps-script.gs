// Google Sheets에 신청 내역을 저장하는 Apps Script (README.md 참고)
const SHEET_NAME = "신청자";

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const p = e.parameter;
    const name = String(p.name || "").trim();
    const phone = String(p.phone || "").replace(/\D/g, "");
    const birth = String(p.birth || "").replace(/\D/g, "");

    if (name.length < 2 || !/^01[016789]\d{7,8}$/.test(phone) || !/^\d{8}$/.test(birth) || p.agreed !== "Y") {
      return json({ ok: false, message: "invalid" });
    }

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(["신청일시", "이름", "휴대폰", "생년월일", "개인정보동의"]);
    }

    const last = sheet.getLastRow();
    if (last > 1) {
      const phones = sheet.getRange(2, 3, last - 1, 1).getValues().flat().map(v => String(v).replace(/\D/g, ""));
      if (phones.includes(phone)) return json({ ok: false, message: "duplicate" });
    }

    const fmtPhone = phone.replace(/^(\d{3})(\d{3,4})(\d{4})$/, "$1-$2-$3");
    const fmtBirth = birth.replace(/^(\d{4})(\d{2})(\d{2})$/, "$1-$2-$3");
    // 앞에 '를 붙여 시트가 숫자/날짜로 자동 변환하지 않게 함
    sheet.appendRow([new Date(), name, "'" + fmtPhone, "'" + fmtBirth, "Y"]);
    return json({ ok: true });
  } finally {
    lock.releaseLock();
  }
}

function json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
