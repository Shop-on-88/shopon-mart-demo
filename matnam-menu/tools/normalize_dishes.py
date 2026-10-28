# 사진 속 그릇(접시·냄비)이 4:3 칸의 같은 비율을 차지하도록 잘라 맞춥니다.
import sys, json
from PIL import Image, ImageDraw
src, dst, boxes_path, fix_path, sheet = sys.argv[1:6]
boxes = json.load(open(boxes_path)); boxes.update(json.load(open(fix_path)))
FILL = 0.86          # 그릇이 칸 너비/높이에서 차지할 비율
names = sorted(boxes)
thumbs = []
for n in names:
    im = Image.open(f'{src}/{n}.jpg').convert('RGB'); W, H = im.size
    x0, y0, x1, y1 = boxes[n]; bw, bh = (x1-x0)*W, (y1-y0)*H; cx, cy = (x0+x1)/2*W, (y0+y1)/2*H
    cw = max(bw / FILL, bh / FILL * 4/3); ch = cw * 3/4
    if cw > W: cw, ch = W, W*3/4
    if ch > H: ch, cw = H, H*4/3
    l = min(max(cx - cw/2, 0), W - cw); t = min(max(cy - ch/2, 0), H - ch)
    out = im.crop((round(l), round(t), round(l+cw), round(t+ch)))
    if out.width > 1200: out = out.resize((1200, 900), Image.LANCZOS)
    out.save(f'{dst}/{n}.jpg', quality=88, optimize=True)
    th = out.copy(); th.thumbnail((200, 150)); thumbs.append((n, th))
cols = 9; sh = Image.new('RGB', (cols*210, ((len(thumbs)+cols-1)//cols)*175), 'white'); d = ImageDraw.Draw(sh)
for k, (n, t) in enumerate(thumbs):
    x, y = (k % cols)*210+5, (k//cols)*175+5; sh.paste(t, (x, y)); d.text((x, y+152), n, fill='black')
sh.save(sheet, quality=82)
