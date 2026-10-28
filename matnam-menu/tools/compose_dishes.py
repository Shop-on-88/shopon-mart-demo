# 오려낸 음식(투명 PNG)을 같은 배경 위에, 그릇 너비가 모두 똑같도록 배치합니다.
# 사용법: python3 tools/compose_dishes.py cutouts img <미리보기.jpg>  (cutouts/ 는 tools/cutout.py 결과)
# 그릇 위치는 tools/vessel_boxes.json(원본 사진 기준 비율 x0,y0,x1,y1)을 씁니다.
import sys, json
from PIL import Image, ImageDraw, ImageFilter
cut, dst, sheet = sys.argv[1], sys.argv[2], sys.argv[3]
boxes = json.load(open("tools/vessel_boxes.json"))
W, H = 1000, 1000
VW, VH = 0.86, 0.88            # 그릇 너비 / 전체(김·반찬 포함) 최대 높이 (칸 대비)
# 흰 접시·그릇은 배경과 함께 지워지는 경우가 있어, 그릇 위치(타원)를 다시 채워 넣습니다.
ROUND = {"kimchi-mari","daktoritang","manghyang","yeolmu-guksu","bibim-guksu","donkatsu","jeyuk-rice","ojingo-rice",
         "bulgogi-rice","fish-katsu","donkatsu-platter","ttongjip-bokkeum","byeongeo","dubu-kimchi","omurice","kimchi-rice",
         "cheese-tteokbokki","ttongjip-twigim","golbaengi","jeyuk-bokkeum","fries","pajeon","tteokbokki","ojingo-kalguksu",
         "sundae","mini-kimbap","chungmu-kimbap","janchi-guksu","jjolmyeon","fried-tofu","dongtae","chik-bibim","chik-mul"}
# 네모 접시·도마는 다시 채우기 어려워, 남은 음식 크기를 기준으로 맞춥니다.
STEAM = {"sundubu","kongnamul","beondegi","steamed-egg","cheonggukjang","doenjang","kimchi-jjigae","seolleongtang","nurungji","hanbang"}
FOOD = {"galchi-gui","nogari","cheese-kimbap","egg-roll","kim-egg-roll","tuna-kimbap"}
BG_TOP, BG_BOT = (243, 235, 220), (228, 216, 196)
bg = Image.new("RGB", (W, H))
d = ImageDraw.Draw(bg)
for y in range(H):
    t = y / (H - 1); d.line([(0, y), (W, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOT)))
thumbs = []
for n, (x0, y0, x1, y1) in sorted(boxes.items()):
    # 색은 원본 사진에서, 오려낼 모양(투명도)은 배경 제거 결과에서 가져옵니다.
    im = Image.open(f"img-src/{n}.jpg").convert("RGBA"); sw, sh = im.size
    im.putalpha(Image.open(f"{cut}/{n}.png").getchannel("A").resize((sw, sh)))
    # 원본 사진 가장자리에서 잘린 부분은 부드럽게 사라지도록 테두리를 흐리게 합니다.
    a = im.getchannel("A"); m = Image.new("L", im.size, 0); f = int(min(sw, sh) * 0.035)
    ImageDraw.Draw(m).rectangle([f, f, sw - f, sh - f], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(f * 0.6))
    im.putalpha(Image.composite(a, Image.new("L", im.size, 0), m))
    if n in STEAM:   # 사진 위쪽에서 잘린 김은 네모나게 보여 지웁니다
        g = Image.new("L", im.size, 255); top = int((y0 + 0.04) * sh)
        ImageDraw.Draw(g).rectangle([0, 0, sw, max(top, 0)], fill=0)
        g = g.filter(ImageFilter.GaussianBlur(sh * 0.02))
        from PIL import ImageChops
        im.putalpha(ImageChops.multiply(im.getchannel("A"), g))
    if n in ROUND:
        e = Image.new("L", im.size, 0)
        ImageDraw.Draw(e).ellipse([x0 * sw, y0 * sh, x1 * sw, y1 * sh], fill=255)
        e = Image.composite(e, Image.new("L", im.size, 0), m)
        from PIL import ImageChops
        im.putalpha(ImageChops.lighter(im.getchannel("A"), e))
    ab = im.getchannel("A").point(lambda v: 255 if v > 140 else 0).getbbox()
    if n in FOOD:
        x0, y0, x1, y1 = ab[0] / sw, ab[1] / sh, ab[2] / sw, ab[3] / sh
    bw = (x1 - x0) * sw
    s = min(VW * W / bw, VH * H / (ab[3] - ab[1]))
    im = im.resize((round(sw * s), round(sh * s)), Image.LANCZOS)
    cx, cy = (x0 + x1) / 2 * sw * s, (ab[1] + ab[3]) / 2 * s
    ox, oy = round(W / 2 - cx), round(H * 0.51 - cy)
    out = bg.copy()
    # 바닥 그림자
    sh_ = Image.new("L", (W, H), 0)
    vx0, vx1 = ox + x0 * sw * s, ox + x1 * sw * s; vy1 = oy + y1 * sh * s
    ImageDraw.Draw(sh_).ellipse([vx0 + 20, vy1 - 60, vx1 - 20, vy1 + 25], fill=90)
    sh_ = sh_.filter(ImageFilter.GaussianBlur(28))
    out.paste((120, 95, 70), (0, 0), sh_)
    out.paste(im, (ox, oy), im)
    out.save(f"{dst}/{n}.jpg", quality=88, optimize=True)
    t = out.copy(); t.thumbnail((200, 150)); thumbs.append((n, t))
cols = 9; sh2 = Image.new("RGB", (cols * 210, ((len(thumbs) + cols - 1) // cols) * 175), "white"); dd = ImageDraw.Draw(sh2)
for k, (n, t) in enumerate(thumbs):
    x, y = (k % cols) * 210 + 5, (k // cols) * 175 + 5; sh2.paste(t, (x, y)); dd.text((x, y + 152), n, fill="black")
sh2.save(sheet, quality=82)
