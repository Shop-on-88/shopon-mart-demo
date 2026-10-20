// 구글 리뷰 자동 연동 (Cloudflare Pages Function: /api/reviews)
// Cloudflare 프로젝트 환경 변수: GOOGLE_PLACES_API_KEY (필수), GOOGLE_PLACE_ID (선택, 없으면 상호로 검색)
// 구글 응답은 6시간 동안 캐시해서 API 호출 비용을 줄입니다.
const QUERY = "In the month of may hair salon 오월에 미용실 Angeles City";
const FIELDS = "id,rating,userRatingCount,reviews,googleMapsUri";
const CACHE_SECONDS = 6 * 60 * 60;

async function findPlaceId(key) {
  const res = await fetch("https://places.googleapis.com/v1/places:searchText", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Goog-Api-Key": key, "X-Goog-FieldMask": "places.id" },
    body: JSON.stringify({ textQuery: QUERY }),
  });
  if (!res.ok) throw new Error(`searchText ${res.status}`);
  const data = await res.json();
  return data.places?.[0]?.id;
}

export async function onRequestGet({ request, env, waitUntil }) {
  const cache = caches.default;
  const cacheKey = new Request(new URL("/api/reviews", request.url).toString());
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  const key = env.GOOGLE_PLACES_API_KEY;
  if (!key) return Response.json({ error: "not_configured" }, { status: 503 });
  try {
    const placeId = env.GOOGLE_PLACE_ID || (await findPlaceId(key));
    if (!placeId) return Response.json({ error: "place_not_found" }, { status: 404 });
    const res = await fetch(`https://places.googleapis.com/v1/places/${placeId}?languageCode=ko`, {
      headers: { "X-Goog-Api-Key": key, "X-Goog-FieldMask": FIELDS },
    });
    if (!res.ok) return Response.json({ error: `google_${res.status}` }, { status: 502 });
    const p = await res.json();
    const body = {
      rating: p.rating ?? null,
      count: p.userRatingCount ?? null,
      mapsUrl: p.googleMapsUri ?? null,
      reviews: (p.reviews || []).map(r => ({
        name: r.authorAttribution?.displayName || "Google user",
        photo: r.authorAttribution?.photoUri || "",
        profile: r.authorAttribution?.uri || "",
        rating: r.rating || 5,
        when: r.relativePublishTimeDescription || "",
        text: r.originalText?.text || r.text?.text || "",
      })),
    };
    const out = Response.json(body, { headers: { "Cache-Control": `public, max-age=${CACHE_SECONDS}` } });
    waitUntil(cache.put(cacheKey, out.clone()));
    return out;
  } catch (e) {
    return Response.json({ error: "fetch_failed" }, { status: 502 });
  }
}
