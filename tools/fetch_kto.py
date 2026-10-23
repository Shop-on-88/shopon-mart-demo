"""한국관광공사 관광사진 정보(PhotoGalleryService1)에서 봉화 사진을 찾는다.

survey: 검색어별 후보를 작게 줄여 tools/kto-candidates/에 저장
pick:   tools/kto-pick.json에 고른 사진을 1200px로 jagalmadang/images/places/에 저장하고 출처를 kto-credits.json에 기록
인증키는 환경변수 TOUR_API_KEY(일반 인증키 Decoding)로 받는다. 로그에 키가 찍히지 않게 URL은 출력하지 않는다.
"""
import io, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from PIL import Image

KEY = "".join(os.environ["TOUR_API_KEY"].split()).strip("'\"")
print("key length", len(KEY), "hex only", all(c in "0123456789abcdefABCDEF" for c in KEY), "has %", "%" in KEY)
API = "https://apis.data.go.kr/B551011/PhotoGalleryService1/gallerySearchList1"
UA = "jagalmadang-site/1.0"
KEYWORDS = {
    "fest-eoun": ["봉화은어축제", "은어축제"],
    "fest-songi": ["봉화송이축제", "송이축제"],
    "chukseosa": ["축서사"],
    "cheongoksan": ["청옥산자연휴양림", "청옥산"],
    "ojeon": ["오전약수"],
    "seokcheon": ["석천정사", "석천계곡"],
    "daksil": ["닭실마을", "청암정"],
    "mansan": ["만산고택"],
    "arboretum": ["국립백두대간수목원", "백두대간수목원"],
    "vtrain": ["백두대간협곡열차", "협곡열차"],
    "hanu": ["봉화한약우", "한약우"],
    "bongseong": ["봉성숯불", "봉성 돼지숯불", "봉성"],
}

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def search(kw, rows=20, page=1):
    q = urllib.parse.urlencode({"serviceKey": KEY, "numOfRows": rows, "pageNo": page, "MobileOS": "ETC",
                                "MobileApp": "jagalmadang", "arrange": "A", "keyword": kw, "_type": "json"})
    raw = get(API + "?" + q)
    try:
        d = json.loads(raw)
    except ValueError:
        print("non-json response:", raw[:200].decode("utf-8", "replace").replace(KEY, "***")); return []
    body = d.get("response", {}).get("body", {})
    items = body.get("items") or {}
    items = items.get("item", []) if isinstance(items, dict) else []
    return items if isinstance(items, list) else [items]

def survey():
    out = "tools/kto-candidates"; os.makedirs(out, exist_ok=True)
    index = {}
    for slug, kws in KEYWORDS.items():
        seen, picks = set(), []
        for kw in kws:
            try: items = search(kw)
            except urllib.error.HTTPError as e:
                print("search fail", slug, kw, e.code, e.read()[:300].decode("utf-8", "replace").replace(KEY, "***")); continue
            except Exception as e: print("search fail", slug, kw, type(e).__name__); continue
            for it in items:
                if it["galContentId"] in seen: continue
                seen.add(it["galContentId"]); picks.append(it)
            time.sleep(0.5)
        picks = picks[:10]
        for i, it in enumerate(picks):
            try:
                im = Image.open(io.BytesIO(get(it["galWebImageUrl"]))).convert("RGB")
                it["size"] = im.size; im.thumbnail((360, 360))
                it["file"] = f"{out}/{slug}-{i}.jpg"; im.save(it["file"], quality=80)
            except Exception as e: print("dl fail", slug, i, type(e).__name__)
        index[slug] = picks
        print(slug, len(picks))
    json.dump(index, open(f"{out}/index.json", "w"), ensure_ascii=False, indent=1)

def catalog():
    """'봉화'가 들어간 사진 전체 목록(이미지는 받지 않음)을 tools/kto-catalog.json에 저장."""
    rows = []
    for kw in ["봉화", "은어", "송이", "수목원", "만산", "청옥산", "한우", "숯불"]:
        for page in range(1, 11):
            try: items = search(kw, rows=100, page=page)
            except Exception as e: print("fail", kw, page, type(e).__name__); break
            if not items: break
            rows += [it for it in items if "봉화" in (it.get("galPhotographyLocation") or "") + (it.get("galTitle") or "")]
            time.sleep(0.3)
    seen, out = set(), []
    for it in rows:
        if it["galContentId"] in seen: continue
        seen.add(it["galContentId"]); out.append(it)
    json.dump(out, open("tools/kto-catalog.json", "w"), ensure_ascii=False, indent=1)
    print("catalog", len(out))

def pick():
    sel = json.load(open("tools/kto-pick.json"))
    out = "jagalmadang/images/places"; os.makedirs(out, exist_ok=True)
    credits = {}
    for slug, it in sel.items():
        im = Image.open(io.BytesIO(get(it["galWebImageUrl"]))).convert("RGB")
        im.thumbnail((1200, 1200)); im.save(f"{out}/{slug}.jpg", quality=82, optimize=True, progressive=True)
        credits[slug] = {"title": it.get("galTitle"), "photographer": it.get("galPhotographer"),
                         "location": it.get("galPhotographyLocation"), "month": it.get("galPhotographyMonth")}
        print(slug, im.size)
    json.dump(credits, open(f"{out}/kto-credits.json", "w"), ensure_ascii=False, indent=1)

{"survey": survey, "pick": pick, "catalog": catalog}[sys.argv[1]]()
