"""위키미디어 공용 Category:Bonghwa County 아래 사진을 작은 크기로 모아 tools/photo-survey/에 저장한다."""
import json, os, re, time, urllib.parse, urllib.request

UA = "jagalmadang-site/1.0 (https://github.com/Shop-on-88/shopon-mart-demo)"
API = "https://commons.wikimedia.org/w/api.php"
OUT = "tools/photo-survey"
EXTRA = ["Baekdudaegan National Arboretum", "Cheongamjeong", "Dalsil village Bonghwa", "Chukseosa",
         "Seokcheonjeongsa", "Mansan Gotaek", "Bonghwa", "봉화군", "Cheongoksan", "V-train Korail Baekdudaegan"]

def api(**p):
    p["format"] = "json"
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(p), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def strip(h):
    return re.sub(r"<[^>]+>", "", h or "").strip()

def walk(cat, depth, files, seen):
    if cat in seen or depth < 0: return
    seen.add(cat)
    cont = {}
    while True:
        d = api(action="query", list="categorymembers", cmtitle=cat, cmlimit="500", cmtype="file|subcat", **cont)
        for m in d["query"]["categorymembers"]:
            if m["ns"] == 14: walk(m["title"], depth - 1, files, seen)
            elif m["ns"] == 6: files.setdefault(m["title"], cat)
        if "continue" not in d: break
        cont = {"cmcontinue": d["continue"]["cmcontinue"]}
        time.sleep(0.5)

def main():
    os.makedirs(OUT, exist_ok=True)
    files = {}
    walk("Category:Bonghwa County", 3, files, set())
    for q in EXTRA:
        try:
            d = api(action="query", list="search", srsearch=q, srnamespace="6", srlimit="20")
            for s in d["query"]["search"]: files.setdefault(s["title"], "search:" + q)
        except Exception as e: print("search fail", q, e)
        time.sleep(0.5)
    files = {t: c for t, c in files.items() if re.search(r"\.(jpe?g|png)$", t, re.I)}
    print("files", len(files))
    titles = list(files)[:400]
    meta = []
    for i in range(0, len(titles), 40):
        chunk = titles[i:i+40]
        d = api(action="query", titles="|".join(chunk), prop="imageinfo", iiprop="url|extmetadata|size", iiurlwidth="320")
        for p in d["query"]["pages"].values():
            if not p.get("imageinfo"): continue
            ii = p["imageinfo"][0]; m = ii.get("extmetadata", {})
            meta.append({"title": p["title"], "cat": files[p["title"]], "w": ii.get("width"), "h": ii.get("height"),
                         "page": ii.get("descriptionurl"), "url": ii.get("url"), "thumb": ii.get("thumburl"),
                         "artist": strip(m.get("Artist", {}).get("value"))[:60],
                         "license": strip(m.get("LicenseShortName", {}).get("value"))})
        time.sleep(0.5)
    for n, it in enumerate(meta):
        it["file"] = f"{OUT}/{n:03d}.jpg"
        try: open(it["file"], "wb").write(get(it["thumb"]))
        except Exception as e: print("dl fail", it["title"], e); it["file"] = None
        time.sleep(0.3)
    json.dump(meta, open(f"{OUT}/index.json", "w"), ensure_ascii=False, indent=1)
    print("saved", len(meta))

main()
