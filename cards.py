"""Image cards for the mart demo bot.

Telegram messages are plain text plus buttons, so every screen that should look like an
app (home dashboard, photo menus, receipt, daily report, stock alert) is drawn here with
Pillow and sent as a photo. Functions take ready-to-print strings and return JPEG bytes;
they know nothing about the database or Telegram.
"""
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

FONT_DIR = Path(__file__).resolve().parent / "fonts"
W = 1080
M = 32  # outer margin

BG = (246, 244, 238)
CARD = (255, 255, 255)
INK = (27, 36, 32)
MUTED = (110, 118, 113)
LINE = (230, 225, 214)
GREEN = (11, 122, 67)
GREEN_DK = (6, 78, 44)
GREEN_SOFT = (226, 242, 232)
ORANGE = (242, 140, 40)
RED = (217, 45, 32)
RED_SOFT = (253, 233, 231)
WHITE = (255, 255, 255)
PAY_COLORS = {"Cash": GREEN, "GCash": (0, 107, 230), "Maya": (0, 168, 150), "Card": ORANGE}


@lru_cache(maxsize=None)
def font(weight, size):
    try:
        return ImageFont.truetype(str(FONT_DIR / f"Pretendard-{weight}.otf"), size)
    except OSError:
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()


def _jpeg(img, quality=88):
    buf = BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def _cover(path, w, h):
    try:
        with Image.open(path) as im:
            return ImageOps.fit(im.convert("RGB"), (w, h), Image.LANCZOS)
    except (OSError, TypeError, AttributeError, ValueError):
        return Image.new("RGB", (w, h), LINE)


def _mask(w, h, r, top_only=False):
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle((0, 0, w - 1, h - 1), r, fill=255)
    if top_only:
        d.rectangle((0, h // 2, w, h), fill=255)
    return m


def _card(canvas, box, radius=22, fill=CARD, shadow=40):
    """Rounded card with a soft drop shadow. canvas must be RGBA."""
    x0, y0, x1, y1 = (int(v) for v in box)
    if shadow:
        pad = 22
        layer = Image.new("RGBA", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle((pad, pad + 6, pad + x1 - x0, pad + 6 + y1 - y0), radius,
                                                fill=(20, 30, 25, shadow))
        canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(9)), (max(x0 - pad, 0), max(y0 - pad, 0)))
    ImageDraw.Draw(canvas).rounded_rectangle((x0, y0, x1, y1), radius, fill=fill)


def _fit(draw, text, weight, size, max_w, min_size=15):
    """Shrink the font until text fits max_w, then ellipsize as a last resort."""
    text = str(text)
    while size > min_size and draw.textlength(text, font=font(weight, size)) > max_w:
        size -= 1
    f = font(weight, size)
    if draw.textlength(text, font=f) > max_w:
        while text and draw.textlength(text + "…", font=f) > max_w:
            text = text[:-1]
        text += "…"
    return text, f


def _pill(draw, xy, text, f, fg, bg, pad=(14, 7), anchor_right=False):
    x, y = xy
    tw = draw.textlength(text, font=f)
    h = f.size + pad[1] * 2
    w = tw + pad[0] * 2
    if anchor_right:
        x -= w
    draw.rounded_rectangle((x, y, x + w, y + h), h // 2, fill=bg)
    draw.text((x + pad[0], y + h / 2), text, font=f, fill=fg, anchor="lm")
    return w, h


def _header(canvas, title, subtitle, accent):
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((M, 34, M + 9, 34 + 74), 5, fill=accent)
    d.text((M + 28, 30), title, font=font("ExtraBold", 46), fill=INK)
    if subtitle:
        d.text((M + 30, 88), subtitle, font=font("SemiBold", 25), fill=MUTED)
    return 140


# ---------------------------------------------------------------- photo menus

def grid(title, subtitle, tiles, accent=GREEN, cols=4):
    """A photo menu. tiles: dicts with img (path), num, name, left (small text), pill (or None), low."""
    g = 16
    tw = (W - 2 * M - (cols - 1) * g) // cols
    ih, lh = tw, 92
    rows = max(1, (len(tiles) + cols - 1) // cols)
    top = 140
    h = top + rows * (ih + lh) + (rows - 1) * g + M + 10
    # A short list (e.g. a 2-item alert) gets a narrower canvas instead of empty space.
    used = min(cols, max(1, len(tiles)))
    width = max(560, 2 * M + used * tw + (used - 1) * g)
    c = Image.new("RGBA", (width, h), BG + (255,))
    _header(c, title, subtitle, accent)
    for i, t in enumerate(tiles):
        x = M + (i % cols) * (tw + g)
        y = top + (i // cols) * (ih + lh + g)
        low = t.get("low")
        _card(c, (x, y, x + tw, y + ih + lh), 18)
        c.paste(_cover(t.get("img"), tw, ih), (x, y), _mask(tw, ih, 18, top_only=True))
        d = ImageDraw.Draw(c)
        r = 23
        cx, cy = x + r + 10, y + r + 10
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=RED if low else accent, outline=WHITE, width=3)
        d.text((cx, cy), str(t["num"]), font=font("ExtraBold", 25), fill=WHITE, anchor="mm")
        name, f = _fit(d, t["name"], "Bold", 23, tw - 24)
        d.text((x + 12, y + ih + 12), name, font=f, fill=INK)
        pill_w = 0
        if t.get("pill"):
            pf = font("Bold", 18)
            pill_w, _ = _pill(d, (x + tw - 10, y + ih + 50), t["pill"], pf,
                              RED if low else GREEN, RED_SOFT if low else GREEN_SOFT, pad=(10, 5), anchor_right=True)
        left, lf = _fit(d, t.get("left", ""), "SemiBold", 20, tw - 30 - pill_w)
        d.text((x + 12, y + ih + 53), left, font=lf, fill=MUTED)
    return _jpeg(c)


# ---------------------------------------------------------------- home dashboard

def home(store_img, eyebrow, store, tagline, date_line, stats):
    """stats: [(label, value, alert?)] - three tiles under the hero."""
    hero_h = 430
    tile_h = 190
    h = hero_h + 30 + tile_h + 40
    c = Image.new("RGBA", (W, h), BG + (255,))

    # Diagonal green gradient hero with soft decorative circles.
    grad = Image.linear_gradient("L").rotate(90).resize((W, hero_h))
    hero = Image.composite(Image.new("RGB", (W, hero_h), GREEN), Image.new("RGB", (W, hero_h), GREEN_DK), grad)
    deco = Image.new("RGBA", (W, hero_h), (0, 0, 0, 0))
    dd = ImageDraw.Draw(deco)
    dd.ellipse((-120, 250, 260, 630), fill=(255, 255, 255, 18))
    dd.ellipse((560, -160, 900, 180), fill=(255, 255, 255, 14))
    hero = Image.alpha_composite(hero.convert("RGBA"), deco)
    c.paste(hero, (0, 0))

    d = ImageDraw.Draw(c)
    pw, ph = 440, 248  # store photos are usually landscape
    px, py = W - M - pw - 8, (hero_h - ph) // 2
    d.rounded_rectangle((px - 8, py - 8, px + pw + 8, py + ph + 8), 30, fill=WHITE)
    c.paste(_cover(store_img, pw, ph), (px, py), _mask(pw, ph, 24))

    text_w = px - M - 50
    _pill(d, (M + 8, 58), eyebrow, font("Bold", 24), GREEN_DK, (255, 255, 255))
    title, tf = _fit(d, store, "ExtraBold", 84, text_w, 40)
    d.text((M + 6, 120), title, font=tf, fill=WHITE)
    tag, gf = _fit(d, tagline, "SemiBold", 32, text_w)
    d.text((M + 8, 232), tag, font=gf, fill=(214, 238, 223))
    d.text((M + 8, 330), date_line, font=font("Bold", 30), fill=WHITE)

    g = 20
    tw = (W - 2 * M - 2 * g) // 3
    y = hero_h + 30
    for i, (label, value, alert) in enumerate(stats):
        x = M + i * (tw + g)
        _card(c, (x, y, x + tw, y + tile_h), 24)
        d = ImageDraw.Draw(c)
        d.rounded_rectangle((x + 26, y + 30, x + 34, y + 62), 4, fill=RED if alert else GREEN)
        d.text((x + 48, y + 46), label, font=font("Bold", 27), fill=MUTED, anchor="lm")
        val, vf = _fit(d, value, "ExtraBold", 58, tw - 52, 30)
        d.text((x + 26, y + 92), val, font=vf, fill=RED if alert else INK)
    return _jpeg(c)


# ---------------------------------------------------------------- receipt

def receipt(store, sub, meta, items, total_label, total, foot, thanks, seed=0):
    """items: [(name, detail, amount)]; meta/foot: [(label, value)]."""
    pw, pm = 760, 56
    cw = W
    row_h = 78
    paper_h = 530 + len(meta) * 40 + len(items) * row_h + len(foot) * 40
    h = paper_h + 2 * 60
    c = Image.new("RGBA", (cw, h), BG + (255,))
    x0, y0 = (cw - pw) // 2, 60
    x1 = x0 + pw

    # Paper with a torn (zigzag) bottom edge and a soft shadow.
    paper = Image.new("L", (pw, paper_h + 20), 0)
    pd = ImageDraw.Draw(paper)
    pd.rectangle((0, 0, pw, paper_h), fill=255)
    tooth = 20
    for i in range(0, pw, tooth):
        pd.polygon([(i, paper_h), (i + tooth / 2, paper_h + 14), (i + tooth, paper_h)], fill=255)
    shadow = Image.new("RGBA", (pw + 60, paper_h + 80), (0, 0, 0, 0))
    shadow.paste((20, 30, 25, 46), (30, 38), paper)
    c.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(12)), (x0 - 30, y0 - 30))
    c.paste(Image.new("RGB", (pw, paper_h + 20), WHITE), (x0, y0), paper)

    d = ImageDraw.Draw(c)
    d.rectangle((x0, y0, x1, y0 + 14), fill=GREEN)
    cx = cw // 2
    y = y0 + 64
    d.text((cx, y), store, font=font("ExtraBold", 50), fill=INK, anchor="mm")
    y += 50
    d.text((cx, y), sub, font=font("SemiBold", 24), fill=MUTED, anchor="mm")
    y += 46

    def dashed(yy):
        for xx in range(x0 + pm, x1 - pm, 18):
            d.line((xx, yy, xx + 9, yy), fill=LINE, width=3)

    dashed(y)
    y += 30
    for label, value in meta:
        d.text((x0 + pm, y), label, font=font("SemiBold", 25), fill=MUTED)
        d.text((x1 - pm, y), value, font=font("SemiBold", 25), fill=INK, anchor="ra")
        y += 40
    y += 6
    dashed(y)
    y += 28
    for name, detail, amount in items:
        amt_w = d.textlength(amount, font=font("Bold", 28))
        nm, nf = _fit(d, name, "Bold", 28, pw - 2 * pm - amt_w - 24)
        d.text((x0 + pm, y), nm, font=nf, fill=INK)
        d.text((x1 - pm, y), amount, font=font("Bold", 28), fill=INK, anchor="ra")
        d.text((x0 + pm, y + 36), detail, font=font("Regular", 23), fill=MUTED)
        y += row_h
    y += 6
    dashed(y)
    y += 34
    d.text((x0 + pm, y + 6), total_label, font=font("Bold", 32), fill=INK)
    d.text((x1 - pm, y - 6), total, font=font("ExtraBold", 54), fill=GREEN, anchor="ra")
    y += 96
    for label, value in foot:
        d.text((x0 + pm, y), label, font=font("SemiBold", 25), fill=MUTED)
        d.text((x1 - pm, y), value, font=font("SemiBold", 25), fill=INK, anchor="ra")
        y += 40
    y += 24
    # Decorative barcode, stable per sale number.
    bx, bw = cx - 200, 400
    state = seed * 2654435761 % 2 ** 32 or 12345
    xx = bx
    while xx < bx + bw:
        state = (1103515245 * state + 12345) % 2 ** 31
        wbar = 2 + state % 5
        if (state >> 7) % 3:
            d.rectangle((xx, y, xx + wbar, y + 64), fill=INK)
        xx += wbar + 2 + (state >> 3) % 3
    y += 96
    d.text((cx, y), thanks, font=font("Bold", 27), fill=GREEN, anchor="mm")
    return _jpeg(c)


# ---------------------------------------------------------------- daily report

def report(title, date, kpis, pay_title, pays, top_title, tops, empty, foot, foot_alert):
    """kpis: [(label, value, color)] x4; pays: [(method, amount_str, fraction)];
    tops: [(name, amount_str, fraction)]."""
    g = 20
    kpi_h = 150
    top_rows = max(1, len(tops))
    h = 170 + 2 * kpi_h + g + 40 + 210 + 70 + top_rows * 84 + 60 + 110
    c = Image.new("RGBA", (W, h), BG + (255,))
    d = ImageDraw.Draw(c)
    d.rectangle((0, 0, W, 150), fill=GREEN_DK)
    d.text((M + 8, 34), title, font=font("ExtraBold", 50), fill=WHITE)
    d.text((M + 10, 98), date, font=font("SemiBold", 27), fill=(198, 230, 211))

    tw = (W - 2 * M - g) // 2
    y = 180
    for i, (label, value, color) in enumerate(kpis):
        x = M + (i % 2) * (tw + g)
        yy = y + (i // 2) * (kpi_h + g)
        _card(c, (x, yy, x + tw, yy + kpi_h), 22)
        d = ImageDraw.Draw(c)
        d.text((x + 28, yy + 26), label, font=font("Bold", 26), fill=MUTED)
        val, vf = _fit(d, value, "ExtraBold", 54, tw - 56, 28)
        d.text((x + 28, yy + 66), val, font=vf, fill=color)
    y += 2 * kpi_h + g + 40

    # Payment split: one stacked bar plus a legend.
    _card(c, (M, y, W - M, y + 190), 22)
    d = ImageDraw.Draw(c)
    d.text((M + 28, y + 24), pay_title, font=font("Bold", 28), fill=INK)
    bx0, bx1, by = M + 28, W - M - 28, y + 78
    d.rounded_rectangle((bx0, by, bx1, by + 30), 15, fill=LINE)
    if pays:
        bar = Image.new("RGBA", (bx1 - bx0, 30), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bar)
        xx = 0
        for method, _, frac in pays:
            wseg = round((bx1 - bx0) * frac)
            bd.rectangle((xx, 0, xx + wseg, 30), fill=PAY_COLORS.get(method, MUTED))
            xx += wseg
        c.paste(bar, (bx0, by), _mask(bx1 - bx0, 30, 15))
        d = ImageDraw.Draw(c)
        lx = bx0
        for method, amount, _ in pays:
            d.ellipse((lx, by + 62, lx + 18, by + 80), fill=PAY_COLORS.get(method, MUTED))
            label = f"{method} {amount}"
            d.text((lx + 28, by + 71), label, font=font("SemiBold", 23), fill=INK, anchor="lm")
            lx += 28 + d.textlength(label, font=font("SemiBold", 23)) + 34
    else:
        d.text((bx0, by + 60), empty, font=font("SemiBold", 23), fill=MUTED)
    y += 190 + g

    # Top products as horizontal bars.
    box_h = 70 + top_rows * 84 + 20
    _card(c, (M, y, W - M, y + box_h), 22)
    d = ImageDraw.Draw(c)
    d.text((M + 28, y + 24), top_title, font=font("Bold", 28), fill=INK)
    yy = y + 80
    if not tops:
        d.text((M + 28, yy), empty, font=font("SemiBold", 23), fill=MUTED)
    for i, (name, amount, frac) in enumerate(tops, 1):
        rank_c = ORANGE if i == 1 else GREEN
        d.ellipse((M + 28, yy, M + 64, yy + 36), fill=rank_c)
        d.text((M + 46, yy + 18), str(i), font=font("ExtraBold", 21), fill=WHITE, anchor="mm")
        amt_w = d.textlength(amount, font=font("Bold", 25))
        nm, nf = _fit(d, name, "Bold", 25, W - 2 * M - 120 - amt_w)
        d.text((M + 80, yy + 18), nm, font=nf, fill=INK, anchor="lm")
        d.text((W - M - 28, yy + 18), amount, font=font("Bold", 25), fill=INK, anchor="rm")
        bx0, bx1 = M + 80, W - M - 28
        d.rounded_rectangle((bx0, yy + 46, bx1, yy + 58), 6, fill=GREEN_SOFT)
        d.rounded_rectangle((bx0, yy + 46, bx0 + max(12, (bx1 - bx0) * frac), yy + 58), 6, fill=rank_c)
        yy += 84
    y += box_h + g

    _pill(d, (M, y + 6), foot, font("Bold", 26), RED if foot_alert else GREEN,
          RED_SOFT if foot_alert else GREEN_SOFT, pad=(22, 12))
    return _jpeg(c.crop((0, 0, W, y + 80)))
