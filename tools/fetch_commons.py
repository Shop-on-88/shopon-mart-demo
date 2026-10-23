"""위키미디어 공용에서 봉화 관광지 사진 후보를 내려받아 tools/photo-candidates/에 저장한다."""
import json, os, re, sys, time, urllib.parse, urllib.request

UA = "jagalmadang-site/1.0 (https://github.com/Shop-on-88/shopon-mart-demo)"
API = "https://commons.wikimedia.org/w/api.php"
OUT = "tools/photo-candidates"

PLACES = {
    "fest-eoun": ["봉화은어축제", "Bonghwa Sweetfish Festival", "Bonghwa Eunuh festival", "은어축제"],
    "fest-songi": ["봉화송이축제", "Bonghwa Pine Mushroom Festival", "Bonghwa Songi festival", "송이축제"],
    "naeseongcheon": ["내성천 봉화", "Naeseongcheon"],
    "chukseosa": ["Chukseosa Temple Bonghwa", "축서사 봉화"],
    "daksil": ["Dalsil Village", "Cheongamjeong Pavilion", "청암정 정자"],
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
