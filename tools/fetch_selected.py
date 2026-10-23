"""고른 위키미디어 공용 사진을 1200px로 받아 jagalmadang/images/places/에 저장하고 출처를 credits.json에 남긴다."""
import json, os, re, time, urllib.parse, urllib.request

UA = "jagalmadang-site/1.0 (https://github.com/Shop-on-88/shopon-mart-demo)"
API = "https://commons.wikimedia.org/w/api.php"
OUT = "jagalmadang/images/places"
PICK = {
    "cheongnyangsan": "File:청량산 ( 8 ).jpg",
    "cheongnyangsa": "File:청량사 경내 Korea - panoramio.jpg",
    "arboretum": "File:국립백두대간수목원 여행자센터.jpg",
    "buncheon": "File:Buncheon Station Platform santa-town 20230501.jpg",
    "seungbu": "File:Korail Yeongdong Line Seungbu Station.jpg",
    "songi": "File:Matsutake.jpg",
    "eoun": "File:Plecoglossus altivelis altivelis ayu.jpg",
}

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def strip(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h or "")).strip()

os.makedirs(OUT, exist_ok=True)
credits = {}
for slug, title in PICK.items():
    q = urllib.parse.urlencode({"action": "query", "format": "json", "titles": title, "prop": "imageinfo",
                                "iiprop": "url|extmetadata", "iiurlwidth": "1200"})
    p = next(iter(json.loads(get(API + "?" + q))["query"]["pages"].values()))
    ii = p["imageinfo"][0]; m = ii.get("extmetadata", {})
    open(f"{OUT}/{slug}.jpg", "wb").write(get(ii["thumburl"]))
    credits[slug] = {"title": title, "page": ii["descriptionurl"],
                     "artist": strip(m.get("Artist", {}).get("value")),
                     "license": strip(m.get("LicenseShortName", {}).get("value")),
                     "license_url": m.get("LicenseUrl", {}).get("value", "")}
    print(slug, credits[slug]["artist"], credits[slug]["license"])
    time.sleep(1)
json.dump(credits, open(f"{OUT}/credits.json", "w"), ensure_ascii=False, indent=1)
