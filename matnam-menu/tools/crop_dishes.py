# 원본 사진(img-src/)을 4:3으로 잘라, 그릇(tools/vessel_boxes.json)이 칸 너비의 같은 비율을 차지하게 맞춥니다.
# 그릇이 원본 사진에 꽉 차 있으면 더 줄일 수 없으므로 사진 전체를 씁니다(잘리는 곳 없음).
# 사용법: python3 tools/crop_dishes.py <미리보기.jpg>
import sys, json
from PIL import Image, ImageDraw
FW, FH = 0.88, 0.90          # 그릇 너비 / 높이 목표(칸 대비)
boxes = json.load(open("tools/vessel_boxes.json"))
thumbs = []
for n, (x0, y0, x1, y1) in sorted(boxes.items()):
    im = Image.open(f"img-src/{n}.jpg").convert("RGB"); W, H = im.size
    bw, bh = (x1 - x0) * W, (y1 - y0) * H; cx, cy = (x0 + x1) / 2 * W, (y0 + y1) / 2 * H
    cw = max(bw / FW, bh / FH * 4 / 3); ch = cw * 3 / 4
    if cw > W: cw, ch = W, W * 3 / 4
    if ch > H: ch, cw = H, H * 4 / 3
    l = min(max(cx - cw / 2, 0), W - cw); t = min(max(cy - ch / 2, 0), H - ch)
    out = im.crop((round(l), round(t), round(l + cw), round(t + ch)))
    if out.width > 1200: out = out.resize((1200, 900), Image.LANCZOS)
    out.save(f"img/{n}.jpg", quality=88, optimize=True)
    th = out.copy(); th.thumbnail((200, 150)); thumbs.append((n, th))
cols = 9; sh = Image.new("RGB", (cols * 210, ((len(thumbs) + cols - 1) // cols) * 175), "white"); d = ImageDraw.Draw(sh)
for k, (n, t) in enumerate(thumbs):
    x, y = (k % cols) * 210 + 5, (k // cols) * 175 + 5; sh.paste(t, (x, y)); d.text((x, y + 152), n, fill="black")
sh.save(sys.argv[1], quality=82)
