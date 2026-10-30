// Google Sheets에 신청 내역을 저장하고, 텔레그램 그룹으로 실시간 알림을 보내는 Apps Script (README.md 참고)
const SHEET_NAME = "신청자";

// 텔레그램 봇 설정 (README.md 의 "텔레그램 실시간 알림" 참고)
// @BotFather 에서 받은 봇 토큰과, 알림을 받을 그룹 채팅의 chat_id 를 넣으세요.
// 둘 다 비워두면 알림 없이 스프레드시트 저장만 합니다.
const TELEGRAM_BOT_TOKEN = "";
const TELEGRAM_CHAT_ID = "";

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const p = e.parameter;
    const name = String(p.name || "").trim();
    const phone = String(p.phone || "").replace(/\D/g, "");
    const birth = String(p.birth || "").replace(/\D/g, "");
    const hotel = String(p.hotel || "").trim();
    const review = String(p.review || "").trim();
    const prize = String(p.prize || "").trim();
    const entryNo = String(p.entryNo || "").trim();

    if (name.length < 2 || !/^01[016789]\d{7,8}$/.test(phone) || !/^\d{8}$/.test(birth) || !hotel || review.length < 10 || p.agreed !== "Y") {
      return json({ ok: false, message: "invalid" });
    }

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(["신청일시", "추첨번호", "이름", "휴대폰", "생년월일", "희망호텔", "리뷰", "체험권(룰렛)", "개인정보동의"]);
    }

    const last = sheet.getLastRow();
    if (last > 1) {
      const phones = sheet.getRange(2, 3, last - 1, 1).getValues().flat().map(v => String(v).replace(/\D/g, ""));
      if (phones.includes(phone)) return json({ ok: false, message: "duplicate" });
    }

    const fmtPhone = phone.replace(/^(\d{3})(\d{3,4})(\d{4})$/, "$1-$2-$3");
    const fmtBirth = birth.replace(/^(\d{4})(\d{2})(\d{2})$/, "$1-$2-$3");
    // 앞에 '를 붙여 시트가 숫자/날짜로 자동 변환하지 않게 함
    sheet.appendRow([new Date(), entryNo, name, "'" + fmtPhone, "'" + fmtBirth, hotel, review, prize, "Y"]);

    notifyTelegram(name, fmtPhone, fmtBirth, hotel, review, prize, entryNo);
    return json({ ok: true });
  } finally {
    lock.releaseLock();
  }
}

function notifyTelegram(name, phone, birth, hotel, review, prize, entryNo) {
  if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) return;
  const text =
    "🏨 *새 숙박권 응모*\n\n" +
    "• 추첨번호: " + entryNo + "\n" +
    "• 이름: " + name + "\n" +
    "• 휴대폰: " + phone + "\n" +
    "• 생년월일: " + birth + "\n" +
    "• 희망 호텔: " + hotel + "\n" +
    "• 리뷰: " + review + "\n" +
    "• 체험권(룰렛): " + prize + "\n" +
    "• 접수: " + Utilities.formatDate(new Date(), "Asia/Seoul", "yyyy-MM-dd HH:mm");
  try {
    UrlFetchApp.fetch("https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage", {
      method: "post",
      payload: { chat_id: TELEGRAM_CHAT_ID, text: text, parse_mode: "Markdown" },
      muteHttpExceptions: true,
    });
  } catch (err) {
    // 알림 실패가 응모 저장을 막지 않도록 무시 (저장은 이미 완료됨)
  }
}

function json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
