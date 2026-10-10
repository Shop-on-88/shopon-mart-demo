"""ShopOn mart demo bot.

A standalone Telegram bot for showing a mart owner what a ShopOn store bot does:
sales with a cart, automatic stock deduction with low-stock alerts, stock-in,
expenses, clock in/out and a daily closing report. It shares no code or data
with b2_erp.py - everything lives in a local SQLite file seeded from products.csv.

Run:  python mart_demo_bot.py      (needs BOT_TOKEN in demo_bot/.env)
"""
import csv
import html
import logging
import os
import sqlite3
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb, InputMediaPhoto, Update
from telegram.error import BadRequest
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters,
)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN")
STORE_NAME = os.getenv("STORE_NAME", "Hanaro Mart")
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "mart_demo.db"))
PRODUCTS_CSV = BASE_DIR / "products.csv"
IMAGE_DIR = BASE_DIR / "images"
TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Manila"))
# Optional: a group chat that also receives low-stock alerts (get the id with /chatid).
ALERT_CHAT_ID = os.getenv("ALERT_CHAT_ID")
# Optional: comma-separated Telegram user ids allowed to /reset. Empty = anyone (fine for a demo).
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x}

PAY_METHODS = ["Cash", "GCash", "Maya", "Card"]
PAGE_SIZE = 8
QTY_EA = [1, 2, 3, 5, 10]
QTY_KG = [0.5, 1, 1.5, 2, 3]
TILE = 300   # px per picture in a menu collage
COLS = 4

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("mart_demo")

# ---------------------------------------------------------------- texts

T = {
    "welcome": {
        "ko": "🛒 <b>{store} 매장 관리봇</b> (ShopOn 데모)\n\n판매·재고·입고·지출·출퇴근·마감을 텔레그램 하나로 관리해요.\n상품명을 바로 입력하면 검색돼요. 예: <code>삼겹살</code>",
        "en": "🛒 <b>{store} Store Bot</b> (ShopOn demo)\n\nSales, stock, deliveries, expenses, attendance and daily closing - all in Telegram.\nType a product name to search. e.g. <code>콜라</code>",
    },
    "menu": {"ko": "📋 <b>메뉴</b>를 선택하세요", "en": "📋 Choose a <b>menu</b>"},
    "btn_sell": {"ko": "🛒 판매", "en": "🛒 Sell"},
    "btn_stock": {"ko": "📦 재고 확인", "en": "📦 Stock"},
    "btn_in": {"ko": "🚚 입고", "en": "🚚 Stock In"},
    "btn_exp": {"ko": "💸 지출", "en": "💸 Expense"},
    "btn_att": {"ko": "👤 출퇴근", "en": "👤 Attendance"},
    "btn_close": {"ko": "📊 오늘 마감", "en": "📊 Daily Close"},
    "btn_lang": {"ko": "🌐 English", "en": "🌐 한국어"},
    "btn_home": {"ko": "🏠 메뉴", "en": "🏠 Menu"},
    "btn_back": {"ko": "◀ 뒤로", "en": "◀ Back"},
    "btn_cart": {"ko": "🧺 장바구니 ({n})", "en": "🧺 Cart ({n})"},
    "btn_pay": {"ko": "💳 결제하기", "en": "💳 Checkout"},
    "btn_more": {"ko": "➕ 상품 더 담기", "en": "➕ Add more"},
    "btn_clear": {"ko": "🗑 비우기", "en": "🗑 Clear"},
    "btn_type": {"ko": "⌨️ 직접 입력", "en": "⌨️ Type qty"},
    "btn_low": {"ko": "⚠️ 부족 상품만 보기", "en": "⚠️ Low stock only"},
    "btn_in_ok": {"ko": "🟢 출근", "en": "🟢 Clock in"},
    "btn_out_ok": {"ko": "🔴 퇴근", "en": "🔴 Clock out"},
    "pick_cat_sell": {"ko": "🛒 <b>판매</b> - 카테고리를 선택하세요", "en": "🛒 <b>Sell</b> - pick a category"},
    "pick_cat_in": {"ko": "🚚 <b>입고</b> - 카테고리를 선택하세요", "en": "🚚 <b>Stock in</b> - pick a category"},
    "pick_cat_stock": {"ko": "📦 <b>재고 확인</b> - 카테고리를 선택하세요\n🔴 부족  🟡 주의  🟢 충분", "en": "📦 <b>Stock</b> - pick a category\n🔴 low  🟡 watch  🟢 ok"},
    "pick_prod": {"ko": "<b>{cat}</b> - 상품을 선택하세요 ({page}/{pages})", "en": "<b>{cat}</b> - pick a product ({page}/{pages})"},
    "card": {
        "ko": "<b>{name}</b>\n💰 {price} / {unit}\n📦 현재 재고: <b>{stock}</b> {unit}\n\n{ask}",
        "en": "<b>{name}</b>\n💰 {price} / {unit}\n📦 In stock: <b>{stock}</b> {unit}\n\n{ask}",
    },
    "ask_sell": {"ko": "몇 개 판매할까요?", "en": "How many to sell?"},
    "ask_sell_kg": {"ko": "몇 kg 판매할까요?", "en": "How many kg to sell?"},
    "ask_in": {"ko": "몇 개 입고됐나요?", "en": "How many came in?"},
    "ask_in_kg": {"ko": "몇 kg 입고됐나요?", "en": "How many kg came in?"},
    "type_qty": {"ko": "⌨️ <b>{name}</b> 수량을 숫자로 입력하세요", "en": "⌨️ Type the quantity for <b>{name}</b>"},
    "bad_qty": {"ko": "⚠️ 수량을 숫자로 입력해주세요. (개 단위는 정수만)", "en": "⚠️ Please type a number. (whole numbers for pieces)"},
    "not_enough": {"ko": "⚠️ 재고가 부족해요: <b>{name}</b> (현재 {stock}{unit}, 요청 {qty}{unit})", "en": "⚠️ Not enough stock: <b>{name}</b> (have {stock}{unit}, need {qty}{unit})"},
    "cart_title": {"ko": "🧺 <b>장바구니</b>", "en": "🧺 <b>Cart</b>"},
    "cart_empty": {"ko": "🧺 장바구니가 비어 있어요.", "en": "🧺 Your cart is empty."},
    "total": {"ko": "합계", "en": "Total"},
    "pick_pay": {"ko": "💳 결제수단을 선택하세요", "en": "💳 Choose payment method"},
    "receipt": {"ko": "✅ <b>판매 완료</b> #{sid}", "en": "✅ <b>Sale complete</b> #{sid}"},
    "staff": {"ko": "담당", "en": "Staff"},
    "pay": {"ko": "결제", "en": "Payment"},
    "low_alert": {"ko": "🚨 <b>재고 부족 알림</b>", "en": "🚨 <b>Low stock alert</b>"},
    "left": {"ko": "남음", "en": "left"},
    "in_done": {"ko": "✅ <b>입고 완료</b>\n{name}: +{qty}{unit}\n📦 현재 재고: <b>{stock}</b>{unit}", "en": "✅ <b>Stock in done</b>\n{name}: +{qty}{unit}\n📦 Now in stock: <b>{stock}</b>{unit}"},
    "stock_none_low": {"ko": "🎉 부족한 상품이 없어요!", "en": "🎉 Nothing is running low!"},
    "stock_low_title": {"ko": "⚠️ <b>부족 상품</b> (최소 재고 이하)", "en": "⚠️ <b>Low stock</b> (at or below minimum)"},
    "exp_ask_item": {"ko": "💸 <b>지출</b> - 항목을 고르거나 직접 입력하세요", "en": "💸 <b>Expense</b> - pick or type an item"},
    "exp_ask_amount": {"ko": "💸 <b>{item}</b> 금액(₱)을 숫자로 입력하세요", "en": "💸 Type the amount (₱) for <b>{item}</b>"},
    "exp_bad_amount": {"ko": "⚠️ 금액을 숫자로 입력해주세요. 예: 1500", "en": "⚠️ Please type a number. e.g. 1500"},
    "exp_pick_pay": {"ko": "💸 <b>{item}</b> {amount}\n결제수단을 선택하세요", "en": "💸 <b>{item}</b> {amount}\nChoose payment method"},
    "exp_done": {"ko": "✅ <b>지출 기록 완료</b>\n{item}: {amount} ({pay})", "en": "✅ <b>Expense saved</b>\n{item}: {amount} ({pay})"},
    "exp_items": {"ko": ["전기세", "운송비", "포장재", "청소용품", "식대"], "en": ["Electricity", "Delivery", "Packaging", "Cleaning", "Meals"]},
    "att_title": {"ko": "👤 <b>출퇴근</b> - 오늘 기록", "en": "👤 <b>Attendance</b> - today"},
    "att_none": {"ko": "아직 기록이 없어요.", "en": "No records yet."},
    "att_in": {"ko": "출근", "en": "in"},
    "att_out": {"ko": "퇴근", "en": "out"},
    "att_done": {"ko": "✅ {name}님 {kind} 기록됐어요 ({time})", "en": "✅ {name} clocked {kind} ({time})"},
    "close_title": {"ko": "📊 <b>{date} 마감 리포트</b>", "en": "📊 <b>Daily report {date}</b>"},
    "close_sales": {"ko": "💰 매출", "en": "💰 Sales"},
    "close_count": {"ko": "건", "en": " orders"},
    "close_top": {"ko": "🏆 많이 팔린 상품 TOP 5", "en": "🏆 Top 5 products"},
    "close_exp": {"ko": "💸 지출", "en": "💸 Expenses"},
    "close_cash": {"ko": "💵 금고 현금 (현금매출 - 현금지출)", "en": "💵 Cash drawer (cash sales - cash expenses)"},
    "close_low": {"ko": "⚠️ 재고 부족 {n}개 상품", "en": "⚠️ {n} products low on stock"},
    "close_none": {"ko": "아직 없음", "en": "none yet"},
    "search_title": {"ko": "🔎 '<b>{q}</b>' 검색 결과 - 선택하면 판매로 이어져요", "en": "🔎 Results for '<b>{q}</b>' - tap to sell"},
    "search_none": {"ko": "🔎 '<b>{q}</b>' 상품을 찾지 못했어요.", "en": "🔎 No product matches '<b>{q}</b>'."},
    "reset_done": {"ko": "♻️ 데모 데이터를 초기화했어요. (상품 {n}개)", "en": "♻️ Demo data reset. ({n} products)"},
    "no_perm": {"ko": "⛔ 권한이 없어요.", "en": "⛔ Not allowed."},
}


def tr(key, lang, **kw):
    s = T[key][lang]
    return s.format(**kw) if kw else s


# ---------------------------------------------------------------- formatting

def money(x):
    sign, x = ("-" if x < 0 else ""), abs(x)
    return f"{sign}₱{x:,.0f}" if float(x).is_integer() else f"{sign}₱{x:,.2f}"


def qty_str(q):
    return f"{q:g}"


def unit_label(unit, lang):
    if unit == "kg":
        return "kg"
    return "개" if lang == "ko" else "pc"


def cat_label(cat, lang):
    # Categories are stored as "<Korean> <English>", e.g. "반찬·즉석 Ready Meals".
    ko, _, en = cat.partition(" ")
    return ko if lang == "ko" or not en else en


def stock_icon(stock, min_stock):
    if stock <= min_stock:
        return "🔴"
    if stock <= min_stock * 2:
        return "🟡"
    return "🟢"


def now():
    return datetime.now(TZ)


def today():
    return now().strftime("%Y-%m-%d")


def esc(s):
    return html.escape(str(s))


# ---------------------------------------------------------------- database

db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row


def init_db(reset=False):
    if reset:
        db.executescript("""
            DROP TABLE IF EXISTS products; DROP TABLE IF EXISTS sales; DROP TABLE IF EXISTS sale_items;
            DROP TABLE IF EXISTS stock_in; DROP TABLE IF EXISTS expenses; DROP TABLE IF EXISTS attendance;
        """)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY, category TEXT, name TEXT, price REAL, unit TEXT,
            stock REAL, min_stock REAL, image TEXT);
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, day TEXT, user_id INTEGER, user_name TEXT,
            total REAL, payment TEXT);
        CREATE TABLE IF NOT EXISTS sale_items (
            sale_id INTEGER, product_id INTEGER, name TEXT, qty REAL, unit_price REAL);
        CREATE TABLE IF NOT EXISTS stock_in (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, day TEXT, user_name TEXT, product_id INTEGER, qty REAL);
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, day TEXT, user_name TEXT, item TEXT,
            amount REAL, payment TEXT);
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, day TEXT, user_id INTEGER, user_name TEXT, kind TEXT);
    """)
    if db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        with open(PRODUCTS_CSV, encoding="utf-8") as f:
            rows = [(int(r["id"]), r["category"], r["name"], float(r["price"]), r["unit"],
                     float(r["stock"]), float(r["min_stock"]), r["image"]) for r in csv.DictReader(f)]
        db.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?,?)", rows)
    db.commit()
    return db.execute("SELECT COUNT(*) FROM products").fetchone()[0]


def categories():
    # Keep the CSV's order so categories appear the way the owner listed them.
    return [r[0] for r in db.execute("SELECT category FROM products GROUP BY category ORDER BY MIN(id)")]


def products_in(cat):
    return db.execute("SELECT * FROM products WHERE category=? ORDER BY id", (cat,)).fetchall()


def product(pid):
    return db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()


# ---------------------------------------------------------------- per-user state

def lang_of(context):
    return context.user_data.get("lang", "ko")


def cart_of(context):
    return context.user_data.setdefault("cart", {})


def user_name(update):
    u = update.effective_user
    return u.full_name or u.username or str(u.id)


# ---------------------------------------------------------------- menu pictures

# Telegram buttons can't hold images, so each menu screen gets one picture: a grid of
# the product photos with numbered badges that match the numbered buttons below it.
_collages = {}   # key -> JPEG bytes
_file_ids = {}   # key -> Telegram file_id, so each grid is uploaded only once


def _badge_font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1 has no scalable default font
        return ImageFont.load_default()


def collage(tiles):
    """tiles: [(image file name, is_low_stock)]. Returns a cache key for photo_media()."""
    key = "|".join(f"{img}:{int(low)}" for img, low in tiles)
    if key in _collages:
        return key
    rows = (len(tiles) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * TILE, rows * TILE), "white")
    draw = ImageDraw.Draw(sheet)
    font = _badge_font(36)
    for i, (img, low) in enumerate(tiles):
        x, y = (i % COLS) * TILE, (i // COLS) * TILE
        path = IMAGE_DIR / (img or "")
        if img and path.is_file():
            with Image.open(path) as im:
                sheet.paste(im.convert("RGB").resize((TILE - 8, TILE - 8)), (x + 4, y + 4))
        r = 27
        cx, cy = x + r + 8, y + r + 8
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill="#d92d20" if low else "#0f766e", outline="white", width=4)
        try:
            draw.text((cx, cy), str(i + 1), fill="white", font=font, anchor="mm")
        except (TypeError, ValueError):  # bitmap fallback font can't anchor
            draw.text((cx - 10, cy - 8), str(i + 1), fill="white", font=font)
    buf = BytesIO()
    sheet.save(buf, "JPEG", quality=82)
    _collages[key] = buf.getvalue()
    return key


def photo_media(key):
    return _file_ids.get(key) or BytesIO(_collages[key])


def remember_photo(key, msg):
    photos = getattr(msg, "photo", None)
    if photos:
        _file_ids[key] = photos[-1].file_id


# ---------------------------------------------------------------- screens

def main_menu(lang, context):
    n = len(cart_of(context))
    rows = [
        [Btn(tr("btn_sell", lang), callback_data="m:sell"), Btn(tr("btn_stock", lang), callback_data="m:stock")],
        [Btn(tr("btn_in", lang), callback_data="m:in"), Btn(tr("btn_exp", lang), callback_data="m:exp")],
        [Btn(tr("btn_att", lang), callback_data="m:att"), Btn(tr("btn_close", lang), callback_data="m:close")],
    ]
    if n:
        rows.insert(0, [Btn(tr("btn_cart", lang, n=n), callback_data="k:view")])
    rows.append([Btn(tr("btn_lang", lang), callback_data="m:lang")])
    return tr("menu", lang), Kb(rows)


def home_row(lang):
    return [Btn(tr("btn_home", lang), callback_data="m:home")]


def category_screen(mode, lang):
    """mode: s = sell, i = stock in, v = view stock."""
    cats = categories()
    rows, row, tiles = [], [], []
    for ci, cat in enumerate(cats):
        prods = products_in(cat)
        tiles.append((prods[0]["image"] if prods else None, False))
        label = f"{ci + 1}. {cat_label(cat, lang)}"
        if mode == "v":
            low = sum(1 for p in prods if p["stock"] <= p["min_stock"])
            label += f" 🔴{low}" if low else ""
        row.append(Btn(label, callback_data=f"c:{mode}:{ci}:0"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if mode == "v":
        rows.append([Btn(tr("btn_low", lang), callback_data="v:low")])
    rows.append(home_row(lang))
    title = {"s": "pick_cat_sell", "i": "pick_cat_in", "v": "pick_cat_stock"}[mode]
    return tr(title, lang), Kb(rows), collage(tiles)


def product_list_screen(mode, ci, page, lang, context):
    cats = categories()
    if ci >= len(cats):
        return category_screen(mode, lang)
    cat = cats[ci]
    prods = products_in(cat)
    if mode == "v":
        lines = [f"📦 <b>{esc(cat_label(cat, lang))}</b>\n"]
        for p in prods:
            u = unit_label(p["unit"], lang)
            lines.append(f"{stock_icon(p['stock'], p['min_stock'])} {esc(p['name'])} - <b>{qty_str(p['stock'])}</b>{u}")
        return "\n".join(lines), Kb([[Btn(tr("btn_back", lang), callback_data="m:stock")], home_row(lang)])

    pages = max(1, (len(prods) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(page, 0), pages - 1)
    rows, tiles = [], []
    for n, p in enumerate(prods[page * PAGE_SIZE:(page + 1) * PAGE_SIZE], 1):
        low = p["stock"] <= p["min_stock"]
        tiles.append((p["image"], low))
        label = f"{n}. {p['name']} · {money(p['price'])}"
        if low:
            label = "🔴 " + label
        rows.append([Btn(label, callback_data=f"p:{mode}:{p['id']}")])
    nav = []
    if page > 0:
        nav.append(Btn("⬅", callback_data=f"c:{mode}:{ci}:{page - 1}"))
    if page < pages - 1:
        nav.append(Btn("➡", callback_data=f"c:{mode}:{ci}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([Btn(tr("btn_back", lang), callback_data="m:sell" if mode == "s" else "m:in")])
    if mode == "s" and cart_of(context):
        rows.append([Btn(tr("btn_cart", lang, n=len(cart_of(context))), callback_data="k:view")])
    rows.append(home_row(lang))
    return tr("pick_prod", lang, cat=esc(cat_label(cat, lang)), page=page + 1, pages=pages), Kb(rows), collage(tiles)


def product_card(mode, p, lang):
    u = unit_label(p["unit"], lang)
    kg = p["unit"] == "kg"
    ask = tr(("ask_sell" if mode == "s" else "ask_in") + ("_kg" if kg else ""), lang)
    text = tr("card", lang, name=esc(p["name"]), price=money(p["price"]), unit=u,
              stock=qty_str(p["stock"]), ask=ask)
    qtys = QTY_KG if kg else QTY_EA
    rows = [[Btn(qty_str(q), callback_data=f"q:{mode}:{p['id']}:{q}") for q in qtys],
            [Btn(tr("btn_type", lang), callback_data=f"x:{mode}:{p['id']}")]]
    cats = categories()
    ci = cats.index(p["category"]) if p["category"] in cats else 0
    rows.append([Btn(tr("btn_back", lang), callback_data=f"c:{mode}:{ci}:0")])
    rows.append(home_row(lang))
    return text, Kb(rows)


def cart_screen(lang, context):
    cart = cart_of(context)
    if not cart:
        return tr("cart_empty", lang), Kb([[Btn(tr("btn_more", lang), callback_data="m:sell")], home_row(lang)])
    lines, total = [tr("cart_title", lang), ""], 0
    for pid, q in cart.items():
        p = product(int(pid))
        sub = p["price"] * q
        total += sub
        lines.append(f"• {esc(p['name'])} × {qty_str(q)}{unit_label(p['unit'], lang)} = {money(sub)}")
    lines += ["", f"<b>{tr('total', lang)}: {money(total)}</b>"]
    rows = [[Btn(tr("btn_pay", lang), callback_data="k:pay")],
            [Btn(tr("btn_more", lang), callback_data="m:sell"), Btn(tr("btn_clear", lang), callback_data="k:clear")],
            home_row(lang)]
    return "\n".join(lines), Kb(rows)


def attendance_screen(lang):
    recs = db.execute("SELECT * FROM attendance WHERE day=? ORDER BY id", (today(),)).fetchall()
    lines = [tr("att_title", lang), ""]
    if not recs:
        lines.append(tr("att_none", lang))
    for r in recs:
        icon = "🟢" if r["kind"] == "in" else "🔴"
        lines.append(f"{icon} {r['ts'][11:16]} {esc(r['user_name'])} {tr('att_' + r['kind'], lang)}")
    rows = [[Btn(tr("btn_in_ok", lang), callback_data="a:in"), Btn(tr("btn_out_ok", lang), callback_data="a:out")],
            home_row(lang)]
    return "\n".join(lines), Kb(rows)


def low_stock_lines(lang):
    low = db.execute("SELECT * FROM products WHERE stock <= min_stock ORDER BY stock").fetchall()
    return [f"🔴 {esc(p['name'])} - <b>{qty_str(p['stock'])}</b>{unit_label(p['unit'], lang)}" for p in low]


def close_report(lang):
    day = today()
    sales = db.execute("SELECT payment, COUNT(*) n, SUM(total) t FROM sales WHERE day=? GROUP BY payment", (day,)).fetchall()
    total = sum(r["t"] for r in sales)
    count = sum(r["n"] for r in sales)
    top = db.execute("""
        SELECT si.name, SUM(si.qty) q, SUM(si.qty * si.unit_price) amt FROM sale_items si
        JOIN sales s ON s.id = si.sale_id WHERE s.day=? GROUP BY si.product_id ORDER BY amt DESC LIMIT 5""",
                     (day,)).fetchall()
    exps = db.execute("SELECT item, payment, SUM(amount) a FROM expenses WHERE day=? GROUP BY item, payment", (day,)).fetchall()
    exp_total = sum(r["a"] for r in exps)
    cash_in = sum(r["t"] for r in sales if r["payment"] == "Cash")
    cash_out = sum(r["a"] for r in exps if r["payment"] == "Cash")

    lines = [tr("close_title", lang, date=day), "",
             f"{tr('close_sales', lang)}: <b>{money(total)}</b> ({count}{tr('close_count', lang)})"]
    for r in sales:
        lines.append(f"   · {r['payment']}: {money(r['t'])} ({r['n']})")
    lines += ["", tr("close_top", lang)]
    if not top:
        lines.append("   " + tr("close_none", lang))
    for i, r in enumerate(top, 1):
        lines.append(f"   {i}. {esc(r['name'])} × {qty_str(r['q'])} = {money(r['amt'])}")
    lines += ["", f"{tr('close_exp', lang)}: <b>{money(exp_total)}</b>"]
    for r in exps:
        lines.append(f"   · {esc(r['item'])} ({r['payment']}): {money(r['a'])}")
    lines += ["", f"{tr('close_cash', lang)}: <b>{money(cash_in - cash_out)}</b>"]
    low = low_stock_lines(lang)
    lines += ["", tr("close_low", lang, n=len(low))] + low[:10]
    return "\n".join(lines), Kb([home_row(lang)])


# ---------------------------------------------------------------- message helpers

async def show(query, text, kb, photo=None):
    """Replace the tapped message with the next screen. A photo message can only be edited
    into another photo, so switching between photo and text screens deletes and re-sends."""
    msg = query.message
    if photo:
        if msg.photo:
            try:
                sent = await msg.edit_media(InputMediaPhoto(photo_media(photo), caption=text, parse_mode="HTML"),
                                            reply_markup=kb)
                remember_photo(photo, sent)
                return
            except BadRequest as e:
                if "not modified" in str(e).lower():
                    return
                log.warning("edit_media failed, re-sending: %s", e)
        await remove(msg)
        sent = await msg.chat.send_photo(photo_media(photo), caption=text, reply_markup=kb, parse_mode="HTML")
        remember_photo(photo, sent)
        return
    if msg.photo:
        try:
            await msg.delete()
        except BadRequest:
            pass
        await msg.chat.send_message(text, reply_markup=kb, parse_mode="HTML")
        return
    try:
        await msg.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


async def send_card(chat, mode, p, lang):
    text, kb = product_card(mode, p, lang)
    img = IMAGE_DIR / (p["image"] or "")
    if p["image"] and img.is_file():
        with open(img, "rb") as f:
            await chat.send_photo(f, caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        await chat.send_message(text, reply_markup=kb, parse_mode="HTML")


async def remove(msg):
    try:
        await msg.delete()
    except BadRequest:
        pass


# ---------------------------------------------------------------- actions

def add_to_cart(context, p, q, lang):
    """Returns an error text, or None when the item went into the cart."""
    cart = cart_of(context)
    want = cart.get(str(p["id"]), 0) + q
    if want > p["stock"]:
        u = unit_label(p["unit"], lang)
        return tr("not_enough", lang, name=esc(p["name"]), stock=qty_str(p["stock"]), qty=qty_str(want), unit=u)
    cart[str(p["id"])] = want
    return None


def stock_in(update, p, q):
    db.execute("UPDATE products SET stock = stock + ? WHERE id=?", (q, p["id"]))
    db.execute("INSERT INTO stock_in (ts, day, user_name, product_id, qty) VALUES (?,?,?,?,?)",
               (now().isoformat(timespec="seconds"), today(), user_name(update), p["id"], q))
    db.commit()
    return product(p["id"])


async def apply_qty(update, context, chat, mode, pid, q):
    lang = lang_of(context)
    p = product(pid)
    if p is None:
        return
    if mode == "s":
        err = add_to_cart(context, p, q, lang)
        text, kb = cart_screen(lang, context)
        await chat.send_message(f"{err}\n\n{text}" if err else text, reply_markup=kb, parse_mode="HTML")
    else:
        p = stock_in(update, p, q)
        u = unit_label(p["unit"], lang)
        cats = categories()
        ci = cats.index(p["category"]) if p["category"] in cats else 0
        kb = Kb([[Btn(tr("btn_in", lang), callback_data=f"c:i:{ci}:0")], home_row(lang)])
        await chat.send_message(tr("in_done", lang, name=esc(p["name"]), qty=qty_str(q), unit=u, stock=qty_str(p["stock"])),
                                reply_markup=kb, parse_mode="HTML")


async def checkout(update, context, query, method):
    lang = lang_of(context)
    cart = cart_of(context)
    if not cart:
        await show(query, *cart_screen(lang, context))
        return
    items = [(product(int(pid)), q) for pid, q in cart.items()]
    for p, q in items:
        if q > p["stock"]:
            text, kb = cart_screen(lang, context)
            err = tr("not_enough", lang, name=esc(p["name"]), stock=qty_str(p["stock"]), qty=qty_str(q),
                     unit=unit_label(p["unit"], lang))
            await show(query, f"{err}\n\n{text}", kb)
            return
    total = sum(p["price"] * q for p, q in items)
    ts = now()
    cur = db.execute("INSERT INTO sales (ts, day, user_id, user_name, total, payment) VALUES (?,?,?,?,?,?)",
                     (ts.isoformat(timespec="seconds"), today(), update.effective_user.id, user_name(update), total, method))
    sid = cur.lastrowid
    for p, q in items:
        db.execute("INSERT INTO sale_items VALUES (?,?,?,?,?)", (sid, p["id"], p["name"], q, p["price"]))
        db.execute("UPDATE products SET stock = stock - ? WHERE id=?", (q, p["id"]))
    db.commit()
    context.user_data["cart"] = {}

    lines = [tr("receipt", lang, sid=sid), f"🕒 {ts.strftime('%Y-%m-%d %H:%M')}", ""]
    for p, q in items:
        lines.append(f"• {esc(p['name'])} × {qty_str(q)}{unit_label(p['unit'], lang)} = {money(p['price'] * q)}")
    lines += ["", f"<b>{tr('total', lang)}: {money(total)}</b>",
              f"{tr('pay', lang)}: {method} · {tr('staff', lang)}: {esc(user_name(update))}"]
    kb = Kb([[Btn(tr("btn_sell", lang), callback_data="m:sell")], home_row(lang)])
    await show(query, "\n".join(lines), kb)

    # Alert on anything this sale pushed to or below its minimum.
    low = []
    for p, q in items:
        after = product(p["id"])
        if after["stock"] <= after["min_stock"]:
            low.append(f"🔴 {esc(after['name'])} - <b>{qty_str(after['stock'])}</b>{unit_label(after['unit'], lang)} {tr('left', lang)}")
    if low:
        alert = tr("low_alert", lang) + "\n" + "\n".join(low)
        await query.message.chat.send_message(alert, parse_mode="HTML")
        if ALERT_CHAT_ID and str(ALERT_CHAT_ID) != str(query.message.chat.id):
            try:
                await context.bot.send_message(ALERT_CHAT_ID, alert, parse_mode="HTML")
            except Exception:
                log.exception("Could not send low-stock alert to ALERT_CHAT_ID")


# ---------------------------------------------------------------- handlers

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    context.user_data.pop("await", None)
    store_img = IMAGE_DIR / "store.jpg"
    welcome = tr("welcome", lang, store=esc(STORE_NAME))
    if store_img.is_file():
        with open(store_img, "rb") as f:
            await update.effective_chat.send_photo(f, caption=welcome, parse_mode="HTML")
    else:
        await update.effective_chat.send_message(welcome, parse_mode="HTML")
    text, kb = main_menu(lang, context)
    await update.effective_chat.send_message(text, reply_markup=kb, parse_mode="HTML")


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("await", None)
    text, kb = main_menu(lang_of(context), context)
    await update.effective_chat.send_message(text, reply_markup=kb, parse_mode="HTML")


async def cmd_chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message(f"chat id: <code>{update.effective_chat.id}</code>", parse_mode="HTML")


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.effective_chat.send_message(tr("no_perm", lang))
        return
    n = init_db(reset=True)
    context.user_data["cart"] = {}
    await update.effective_chat.send_message(tr("reset_done", lang, n=n))


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = lang_of(context)
    parts = query.data.split(":")
    kind = parts[0]
    chat = query.message.chat
    context.user_data.pop("await", None)

    if kind == "m":
        what = parts[1]
        if what == "lang":
            context.user_data["lang"] = lang = "en" if lang == "ko" else "ko"
            await show(query, *main_menu(lang, context))
        elif what == "home":
            await show(query, *main_menu(lang, context))
        elif what == "sell":
            await show(query, *category_screen("s", lang))
        elif what == "in":
            await show(query, *category_screen("i", lang))
        elif what == "stock":
            await show(query, *category_screen("v", lang))
        elif what == "exp":
            items = tr("exp_items", lang)
            rows = [[Btn(it, callback_data=f"ei:{i}") for i, it in enumerate(items[:3])],
                    [Btn(it, callback_data=f"ei:{i + 3}") for i, it in enumerate(items[3:])],
                    home_row(lang)]
            context.user_data["await"] = ("exp_item",)
            await show(query, tr("exp_ask_item", lang), Kb(rows))
        elif what == "att":
            await show(query, *attendance_screen(lang))
        elif what == "close":
            await show(query, *close_report(lang))

    elif kind == "c":
        mode, ci, page = parts[1], int(parts[2]), int(parts[3])
        await show(query, *product_list_screen(mode, ci, page, lang, context))

    elif kind == "p":
        mode, pid = parts[1], int(parts[2])
        p = product(pid)
        if p:
            await remove(query.message)
            await send_card(chat, mode, p, lang)

    elif kind == "q":
        mode, pid, q = parts[1], int(parts[2]), float(parts[3])
        await remove(query.message)
        await apply_qty(update, context, chat, mode, pid, q)

    elif kind == "x":
        mode, pid = parts[1], int(parts[2])
        p = product(pid)
        if p:
            context.user_data["await"] = ("qty", mode, pid)
            await show(query, tr("type_qty", lang, name=esc(p["name"])), Kb([home_row(lang)]))

    elif kind == "k":
        what = parts[1]
        if what == "view":
            await show(query, *cart_screen(lang, context))
        elif what == "clear":
            context.user_data["cart"] = {}
            await show(query, *cart_screen(lang, context))
        elif what == "pay":
            text, _ = cart_screen(lang, context)
            rows = [[Btn(m, callback_data=f"y:{m}") for m in PAY_METHODS],
                    [Btn(tr("btn_back", lang), callback_data="k:view")]]
            await show(query, f"{text}\n\n{tr('pick_pay', lang)}", Kb(rows))

    elif kind == "y":
        await checkout(update, context, query, parts[1])

    elif kind == "v" and parts[1] == "low":
        low = low_stock_lines(lang)
        text = tr("stock_low_title", lang) + "\n\n" + "\n".join(low) if low else tr("stock_none_low", lang)
        rows = [[Btn(tr("btn_in", lang), callback_data="m:in")],
                [Btn(tr("btn_back", lang), callback_data="m:stock")], home_row(lang)]
        await show(query, text, Kb(rows))

    elif kind == "ei":
        item = tr("exp_items", lang)[int(parts[1])]
        context.user_data["await"] = ("exp_amount", item)
        await show(query, tr("exp_ask_amount", lang, item=esc(item)), Kb([home_row(lang)]))

    elif kind == "e":
        pending = context.user_data.pop("exp_pending", None)
        if not pending:
            await show(query, *main_menu(lang, context))
            return
        item, amount = pending
        db.execute("INSERT INTO expenses (ts, day, user_name, item, amount, payment) VALUES (?,?,?,?,?,?)",
                   (now().isoformat(timespec="seconds"), today(), user_name(update), item, amount, parts[1]))
        db.commit()
        await show(query, tr("exp_done", lang, item=esc(item), amount=money(amount), pay=parts[1]),
                   Kb([[Btn(tr("btn_exp", lang), callback_data="m:exp")], home_row(lang)]))

    elif kind == "a":
        ts = now()
        db.execute("INSERT INTO attendance (ts, day, user_id, user_name, kind) VALUES (?,?,?,?,?)",
                   (ts.isoformat(timespec="seconds"), today(), update.effective_user.id, user_name(update), parts[1]))
        db.commit()
        text, kb = attendance_screen(lang)
        done = tr("att_done", lang, name=esc(user_name(update)), kind=tr("att_" + parts[1], lang), time=ts.strftime("%H:%M"))
        await show(query, f"{done}\n\n{text}", kb)


def parse_number(text):
    try:
        return float(text.replace(",", "").replace("₱", "").strip())
    except ValueError:
        return None


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    text = update.message.text.strip()
    chat = update.effective_chat
    waiting = context.user_data.get("await")

    if waiting and waiting[0] == "qty":
        _, mode, pid = waiting
        p = product(pid)
        q = parse_number(text)
        if p is None or q is None or q <= 0 or (p["unit"] != "kg" and not q.is_integer()):
            await chat.send_message(tr("bad_qty", lang))
            return
        context.user_data.pop("await", None)
        await apply_qty(update, context, chat, mode, pid, q)
        return

    if waiting and waiting[0] == "exp_item":
        context.user_data["await"] = ("exp_amount", text[:60])
        await chat.send_message(tr("exp_ask_amount", lang, item=esc(text[:60])), reply_markup=Kb([home_row(lang)]),
                                parse_mode="HTML")
        return

    if waiting and waiting[0] == "exp_amount":
        amount = parse_number(text)
        if amount is None or amount <= 0:
            await chat.send_message(tr("exp_bad_amount", lang))
            return
        item = waiting[1]
        context.user_data.pop("await", None)
        context.user_data["exp_pending"] = (item, amount)
        rows = [[Btn(m, callback_data=f"e:{m}") for m in PAY_METHODS], home_row(lang)]
        await chat.send_message(tr("exp_pick_pay", lang, item=esc(item), amount=money(amount)),
                                reply_markup=Kb(rows), parse_mode="HTML")
        return

    # Anything else is treated as a product search that leads straight into a sale.
    hits = db.execute("SELECT * FROM products WHERE name LIKE ? ORDER BY id LIMIT 10", (f"%{text}%",)).fetchall()
    if not hits:
        _, kb = main_menu(lang, context)
        await chat.send_message(tr("search_none", lang, q=esc(text)), reply_markup=kb, parse_mode="HTML")
        return
    rows = [[Btn(f"{n}. {p['name']} · {money(p['price'])}", callback_data=f"p:s:{p['id']}")]
            for n, p in enumerate(hits, 1)]
    rows.append(home_row(lang))
    key = collage([(p["image"], p["stock"] <= p["min_stock"]) for p in hits])
    sent = await chat.send_photo(photo_media(key), caption=tr("search_title", lang, q=esc(text)),
                                 reply_markup=Kb(rows), parse_mode="HTML")
    remember_photo(key, sent)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error("Unhandled error", exc_info=context.error)


def build_app():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("chatid", cmd_chatid))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)
    return app


def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is missing. Copy .env.example to .env and put the demo bot token in it.")
    n = init_db()
    log.info("Loaded %d products for %s", n, STORE_NAME)
    build_app().run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
