// 버튼 클릭·방문 수 집계 (Cloudflare Pages Function: POST /api/track)
// Cloudflare 프로젝트 바인딩: KV 네임스페이스를 변수 이름 STATS 로 연결해야 저장됩니다.
const EVENTS = ["visit", "call", "text", "kakao", "messenger", "map", "chat", "facebook", "instagram"];

export function manilaDate(d = new Date()) {
  return new Date(d.getTime() + 8 * 3600 * 1000).toISOString().slice(0, 10);
}

export async function onRequestPost({ request, env }) {
  if (!env.STATS) return new Response(null, { status: 204 });
  let e = "";
  try { e = (await request.json()).e; } catch {}
  if (!EVENTS.includes(e)) return new Response(null, { status: 204 });
  const key = `d:${manilaDate()}:${e}`;
  const n = parseInt((await env.STATS.get(key)) || "0", 10) + 1;
  await env.STATS.put(key, String(n));
  return new Response(null, { status: 204 });
}
