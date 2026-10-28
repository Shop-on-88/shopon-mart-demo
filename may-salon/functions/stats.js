// 사장님 전용 통계 페이지 (GET /stats)
// Cloudflare 프로젝트: KV 바인딩 STATS, 비밀 STATS_PASSWORD 필요. 아이디는 아무거나, 비밀번호는 STATS_PASSWORD.
import { manilaDate } from "./api/track.js";

const COLS = [["visit", "Visitors", "방문"], ["call", "Call", "전화"], ["kakao", "KakaoTalk", "카톡"], ["messenger", "Messenger", "메신저"],
  ["text", "Text", "문자"], ["map", "Map", "길찾기"], ["chat", "Chat open", "상담창"], ["facebook", "Facebook", "페이스북"], ["instagram", "Instagram", "인스타"]];

function page(body) {
  return new Response(`<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>오월에 통계</title><meta name="robots" content="noindex">
<style>
body{margin:0;background:#0e0c0a;color:#f2e8d6;font:15px/1.6 system-ui,-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;padding:24px 16px}
h1{font-size:22px;color:#e3c88d;margin:0 0 4px}p{color:#b0a089;margin:0 0 20px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:24px}
.card{background:#17130f;border:1px solid #3a2f22;border-radius:8px;padding:14px}.card b{display:block;font-size:13px;color:#b0a089;font-weight:500}
.card span{font-size:24px;color:#e3c88d;font-variant-numeric:tabular-nums}.card small{color:#b0a089}
.wrap{overflow-x:auto;border:1px solid #3a2f22;border-radius:8px}
table{border-collapse:collapse;width:100%;min-width:640px;font-variant-numeric:tabular-nums}
th,td{padding:9px 12px;border-bottom:1px solid #2a221a;text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}
th{background:#17130f;color:#c9a45c;font-weight:600}tr.sum td{color:#e3c88d;font-weight:700;background:#17130f}
</style></head><body>${body}</body></html>`, { headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
}

export async function onRequestGet({ request, env }) {
  const pw = env.STATS_PASSWORD;
  const auth = request.headers.get("Authorization") || "";
  const given = auth.startsWith("Basic ") ? (atob(auth.slice(6)).split(":").slice(1).join(":")) : null;
  if (!pw || given !== pw) {
    return new Response("Password required", { status: 401, headers: { "WWW-Authenticate": 'Basic realm="maysalon stats", charset="UTF-8"' } });
  }
  if (!env.STATS) return page("<h1>오월에 홈페이지 통계</h1><p>저장 공간(KV) 연결이 아직 안 됐어요. Cloudflare에서 STATS 바인딩을 추가해 주세요.</p>");

  const days = [];
  const now = new Date();
  for (let i = 0; i < 30; i++) days.push(manilaDate(new Date(now.getTime() - i * 864e5)));
  const rows = await Promise.all(days.map(async d => {
    const vals = await Promise.all(COLS.map(([k]) => env.STATS.get(`d:${d}:${k}`)));
    return [d, vals.map(v => parseInt(v || "0", 10))];
  }));
  const sum = (n) => rows.slice(0, n).reduce((a, [, v]) => a.map((x, i) => x + v[i]), COLS.map(() => 0));
  const today = sum(1), week = sum(7), month = sum(30);
  const card = (i) => `<div class="card"><b>${COLS[i][2]}</b><span>${today[i]}</span> <small>오늘 · 7일 ${week[i]} · 30일 ${month[i]}</small></div>`;
  const head = `<tr><th>날짜</th>${COLS.map(c => `<th>${c[2]}</th>`).join("")}</tr>`;
  const body = rows.map(([d, v]) => `<tr><td>${d.slice(5).replace("-", "/")}</td>${v.map(x => `<td>${x || "·"}</td>`).join("")}</tr>`).join("");
  const total = `<tr class="sum"><td>30일 합계</td>${month.map(x => `<td>${x}</td>`).join("")}</tr>`;
  return page(`<h1>오월에 홈페이지 통계</h1><p>필리핀 시간 기준 · 오늘 ${days[0]} · 새로고침하면 최신 숫자로 바뀌어요</p>
<div class="cards">${[0, 1, 2, 3, 5].map(card).join("")}</div>
<div class="wrap"><table>${head}${total}${body}</table></div>`);
}
