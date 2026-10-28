# 사진에서 그릇(접시·냄비)만 오려내 투명 PNG로 저장합니다. 원본: img-src/, 결과: 두 번째 인자 폴더
import sys, glob, os
from rembg import remove, new_session
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
only = set(sys.argv[3:])
sess = new_session("isnet-general-use")
for p in sorted(glob.glob(src + "/*.jpg")):
    n = os.path.basename(p)[:-4]
    if only and n not in only: continue
    im = Image.open(p).convert("RGB")
    out = remove(im, session=sess, post_process_mask=True)
    out.save(f"{dst}/{n}.png"); print(n, flush=True)
