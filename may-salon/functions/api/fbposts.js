// 페이스북 페이지 최신 게시물 자동 연동 (Cloudflare Pages Function: /api/fbposts)
// Cloudflare 프로젝트 환경 변수: FB_PAGE_TOKEN (필수, 만료 없는 페이지 액세스 토큰), FB_PAGE_ID (선택)
// 페이스북 응답은 1시간 동안 캐시합니다.
const PAGE_ID = "1378115242050188";
const CACHE_SECONDS = 60 * 60;

export async function onRequestGet({ request, env, waitUntil }) {
  const cache = caches.default;
  const cacheKey = new Request(new URL("/api/fbposts", request.url).toString());
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  const token = env.FB_PAGE_TOKEN;
  if (!token) return Response.json({ error: "not_configured" }, { status: 503 });
  const id = env.FB_PAGE_ID || PAGE_ID;
  const url = `https://graph.facebook.com/v21.0/${id}/posts?fields=message,created_time,permalink_url,full_picture&limit=6&access_token=${encodeURIComponent(token)}`;
  try {
    const res = await fetch(url);
    if (!res.ok) return Response.json({ error: `facebook_${res.status}` }, { status: 502 });
    const data = await res.json();
    const posts = (data.data || [])
      .filter(p => p.full_picture || p.message)
      .map(p => ({ text: p.message || "", image: p.full_picture || "", url: p.permalink_url || "", time: p.created_time }));
    const out = Response.json({ posts }, { headers: { "Cache-Control": `public, max-age=${CACHE_SECONDS}` } });
    waitUntil(cache.put(cacheKey, out.clone()));
    return out;
  } catch (e) {
    return Response.json({ error: "fetch_failed" }, { status: 502 });
  }
}
