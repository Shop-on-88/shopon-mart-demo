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

def thumbs():
    """kto-catalog.json에서 고를 제목들의 사진을 작게 받아 tools/kto-candidates/에 저장."""
    want = ["아름다운 축서사", "오전약수탕", "석천정사", "닭실마을", "청암정", "봉화 청량사", "가을빛 따스한 청량사탑", "바래미 전통마을", "도암정"]
    out = "tools/kto-candidates"; os.makedirs(out, exist_ok=True)
    cat = json.load(open("tools/kto-catalog.json")); index = []
    for it in cat:
        if it["galTitle"] not in want: continue
        try:
            im = Image.open(io.BytesIO(get(it["galWebImageUrl"]))).convert("RGB"); im.thumbnail((300, 300))
            it["file"] = f"{out}/{it['galContentId']}.jpg"; im.save(it["file"], quality=78); index.append(it)
        except Exception as e: print("dl fail", type(e).__name__)
    json.dump(index, open(f"{out}/index.json", "w"), ensure_ascii=False, indent=1)
    print("thumbs", len(index))

def kor(op, **params):
    """국문 관광정보 서비스(KorService2) 호출."""
    q = urllib.parse.urlencode(dict(serviceKey=KEY, MobileOS="ETC", MobileApp="jagalmadang", _type="json", numOfRows=50, pageNo=1, **params))
    d = None
    for svc, o in (("KorService2", op), ("KorService1", op.rstrip("2") + "1")):
        try:
            d = json.loads(get(f"https://apis.data.go.kr/B551011/{svc}/{o}?" + q)); print("using", svc); break
        except urllib.error.HTTPError as e:
            print(svc, o, e.code, e.read()[:200].decode("utf-8", "replace").replace(KEY, "***"))
    if d is None: return []
    items = (d.get("response", {}).get("body", {}).get("items") or {})
    items = items.get("item", []) if isinstance(items, dict) else []
    return items if isinstance(items, list) else [items]

def festival():
    """봉화 은어·송이 축제의 상세 이미지를 작게 받아 tools/kto-candidates/에 저장."""
    out = "tools/kto-candidates"; os.makedirs(out, exist_ok=True); index = []
    for kw in ["봉화은어축제", "봉화송이축제"]:
        for c in kor("searchKeyword2", keyword=kw, contentTypeId=15):
            print(kw, c.get("contentid"), c.get("title"), c.get("cpyrhtDivCd"))
            imgs = kor("detailImage2", contentId=c["contentid"], imageYN="Y")
            if c.get("firstimage"): imgs = [{"originimgurl": c["firstimage"], "imgname": "firstimage", "cpyrhtDivCd": c.get("cpyrhtDivCd")}] + imgs
            for i, im in enumerate(imgs):
                try:
                    pic = Image.open(io.BytesIO(get(im["originimgurl"]))).convert("RGB")
                    im["size"] = pic.size; pic.thumbnail((360, 360))
                    im["file"] = f"{out}/{c['contentid']}-{i}.jpg"; pic.save(im["file"], quality=80)
                    im["festival"] = kw; im["contentid"] = c["contentid"]; index.append(im)
                except Exception as e: print("dl fail", type(e).__name__)
            time.sleep(0.5)
    json.dump(index, open(f"{out}/index.json", "w"), ensure_ascii=False, indent=1)
    print("festival images", len(index))

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

{"survey": survey, "pick": pick, "catalog": catalog, "thumbs": thumbs, "festival": festival}[sys.argv[1]]()
