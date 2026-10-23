"""위키미디어 공용에서 봉화 관광지 사진 후보를 내려받아 tools/photo-candidates/에 저장한다."""
import json, os, re, sys, time, urllib.parse, urllib.request

UA = "jagalmadang-site/1.0 (https://github.com/Shop-on-88/shopon-mart-demo)"
API = "https://commons.wikimedia.org/w/api.php"
OUT = "tools/photo-candidates"

PLACES = {
    "cheongnyangsan": ["청량산 하늘다리", "Cheongnyangsan", "청량산"],
    "cheongnyangsa": ["청량사 봉화", "Cheongnyangsa"],
    "chukseosa": ["축서사", "Chukseosa"],
    "cheongoksan": ["청옥산자연휴양림", "Cheongoksan"],
    "ojeon": ["오전약수", "Ojeon mineral spring"],
    "seokcheon": ["석천정사", "석천계곡 봉화"],
    "arboretum": ["국립백두대간수목원", "Baekdudaegan National Arboretum"],
    "buncheon": ["분천역", "Buncheon Station", "분천 산타마을"],
    "vtrain": ["백두대간협곡열차", "V-train Korea", "Baekdudaegan Canyon Train"],
    "seungbu": ["승부역", "Seungbu Station"],
    "daksil": ["청암정", "닭실마을", "Cheongamjeong"],
    "mansan": ["만산고택", "Mansan Gotaek"],
    "songi": ["Tricholoma matsutake", "송이버섯"],
    "eoun": ["Plecoglossus altivelis", "은어"],
}

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def strip(html):
    return re.sub(r"<[^>]+>", "", html or "").strip()

def search(q):
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{q} filetype:bitmap", "gsrnamespace": "6", "gsrlimit": "8",
        "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": "1200",
    }
    data = json.loads(get(API + "?" + urllib.parse.urlencode(params)))
    pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    return pages

def main():
    os.makedirs(OUT, exist_ok=True)
    index = {}
    for slug, queries in PLACES.items():
        seen, items = set(), []
        for q in queries:
            try:
                pages = search(q)
            except Exception as e:
                print("search fail", slug, q, e); continue
            for p in pages:
                t = p["title"]
                if t in seen or not p.get("imageinfo"): continue
                ii = p["imageinfo"][0]
                if ii.get("width", 0) < 800: continue
                seen.add(t)
                m = ii.get("extmetadata", {})
                items.append({
                    "title": t, "page": ii.get("descriptionurl"), "thumb": ii.get("thumburl"),
                    "artist": strip(m.get("Artist", {}).get("value")),
                    "license": strip(m.get("LicenseShortName", {}).get("value")),
                    "desc": strip(m.get("ImageDescription", {}).get("value"))[:200],
                })
            time.sleep(1)
        items = items[:6]
        for i, it in enumerate(items):
            fn = f"{OUT}/{slug}-{i}.jpg"
            try:
                open(fn, "wb").write(get(it["thumb"])); it["file"] = fn
            except Exception as e:
                print("dl fail", it["title"], e)
            time.sleep(1)
        index[slug] = items
        print(slug, len(items))
    json.dump(index, open(f"{OUT}/index.json", "w"), ensure_ascii=False, indent=1)

main()
