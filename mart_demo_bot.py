"""ShopOn mart demo bot.

A standalone Telegram bot for showing a mart owner what a ShopOn store bot does:
sales with a cart, automatic stock deduction with low-stock alerts, stock-in,
expenses, clock in/out and a daily closing report. It shares no code or data
with b2_erp.py - everything lives in a local SQLite file seeded from products.csv.

Screens that should look like an app (home dashboard, photo menus, receipt, report,
stock alert) are drawn as images by cards.py and sent as photos.

Run:  python mart_demo_bot.py      (needs BOT_TOKEN in demo_bot/.env)
"""
import csv
import hashlib
import html
import logging
import os
import random
import sqlite3
from collections import OrderedDict
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import BotCommand, InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb, InputMediaPhoto, Update
from telegram.error import BadRequest
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters,
)

import cards

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
LINE = "━━━━━━━━━━━━━━"

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("mart_demo")

# ---------------------------------------------------------------- texts

T = {
    "welcome": {
        "ko": "👋 <b>{store}</b>에 오신 걸 환영해요!\n\n판매 · 재고 · 입고 · 지출 · 출퇴근 · 마감까지\n텔레그램 하나로 매장을 관리하는 <b>ShopOn 데모</b>예요.\n\n💡 채팅창에 상품명을 치면 바로 검색돼요. 예: <code>삼겹살</code>",
        "en": "👋 Welcome to <b>{store}</b>!\n\nSales, stock, deliveries, expenses, attendance and closing -\nyour whole store in Telegram. This is the <b>ShopOn demo</b>.\n\n💡 Type a product name to search. e.g. <code>콜라</code>",
    },
    "menu": {"ko": "📋 <b>무엇을 할까요?</b>", "en": "📋 <b>What would you like to do?</b>"},
    "btn_sell": {"ko": "🛒 판매하기", "en": "🛒 New sale"},
    "btn_stock": {"ko": "📦 재고 확인", "en": "📦 Stock"},
    "btn_in": {"ko": "🚚 입고", "en": "🚚 Stock in"},
    "btn_exp": {"ko": "💸 지출", "en": "💸 Expense"},
    "btn_att": {"ko": "👤 출퇴근", "en": "👤 Attendance"},
    "btn_close": {"ko": "📊 오늘 마감 리포트", "en": "📊 Daily report"},
    "btn_lang": {"ko": "🌐 English", "en": "🌐 한국어"},
    "btn_home": {"ko": "🏠 홈", "en": "🏠 Home"},
    "btn_back": {"ko": "◀ 뒤로", "en": "◀ Back"},
    "btn_cart": {"ko": "🧺 장바구니 보기 ({n})", "en": "🧺 View cart ({n})"},
    "btn_pay": {"ko": "💳 결제하기", "en": "💳 Checkout"},
    "btn_more": {"ko": "➕ 더 담기", "en": "➕ Add more"},
    "btn_clear": {"ko": "🗑 비우기", "en": "🗑 Clear"},
    "btn_type": {"ko": "⌨️ 직접 입력", "en": "⌨️ Type qty"},
    "btn_low": {"ko": "⚠️ 부족 상품만 보기", "en": "⚠️ Low stock only"},
    "btn_in_ok": {"ko": "🟢 출근", "en": "🟢 Clock in"},
    "btn_out_ok": {"ko": "🔴 퇴근", "en": "🔴 Clock out"},
    "btn_restock": {"ko": "🚚 바로 입고하기", "en": "🚚 Restock now"},
    "home_eyebrow": {"ko": "ShopOn 매장관리", "en": "ShopOn Store Manager"},
    "home_tag": {"ko": "판매 · 재고 · 마감을 텔레그램 하나로", "en": "Sales · Stock · Closing in Telegram"},
    "stat_sales": {"ko": "오늘 매출", "en": "Today's sales"},
    "stat_orders": {"ko": "주문", "en": "Orders"},
    "stat_low": {"ko": "재고 부족", "en": "Low stock"},
    "n_orders": {"ko": "{n}건", "en": "{n}"},
    "n_items": {"ko": "{n}개", "en": "{n}"},
    "grid_cats_sell": {"ko": "판매하기", "en": "New sale"},
    "grid_cats_in": {"ko": "입고 등록", "en": "Stock in"},
    "grid_cats_stock": {"ko": "재고 확인", "en": "Stock"},
    "grid_cats_sub": {"ko": "카테고리를 골라주세요", "en": "Pick a category"},
    "grid_prod_sub": {"ko": "{page}/{pages} · 상품을 골라주세요", "en": "{page}/{pages} · Pick a product"},
    "grid_stock_sub": {"ko": "{page}/{pages} · 누르면 바로 입고할 수 있어요", "en": "{page}/{pages} · Tap to restock"},
    "cat_count": {"ko": "상품 {n}개", "en": "{n} items"},
    "cat_low": {"ko": "부족 {n}", "en": "{n} low"},
    "pill_low": {"ko": "부족 {q}", "en": "Low {q}"},
    "cap_cats_sell": {"ko": "🛒 <b>판매하기</b> · 카테고리를 골라주세요", "en": "🛒 <b>New sale</b> · pick a category"},
    "cap_cats_in": {"ko": "🚚 <b>입고 등록</b> · 카테고리를 골라주세요", "en": "🚚 <b>Stock in</b> · pick a category"},
    "cap_cats_stock": {"ko": "📦 <b>재고 확인</b> · 카테고리를 골라주세요\n🔴 숫자 = 최소 재고 이하 상품", "en": "📦 <b>Stock</b> · pick a category\n🔴 = at or below minimum"},
    "cap_prod": {"ko": "<b>{cat}</b> · 번호를 눌러 선택하세요", "en": "<b>{cat}</b> · tap a number"},
    "card": {
        "ko": "<b>{name}</b>\n{line}\n💰 가격  <b>{price}</b> / {unit}\n📦 재고  <b>{stock}{unit}</b>{low}\n{line}\n{ask}",
        "en": "<b>{name}</b>\n{line}\n💰 Price  <b>{price}</b> / {unit}\n📦 Stock  <b>{stock}{unit}</b>{low}\n{line}\n{ask}",
    },
    "card_low": {"ko": "  🔴 부족", "en": "  🔴 low"},
    "ask_sell": {"ko": "👇 몇 개 판매할까요?", "en": "👇 How many to sell?"},
    "ask_sell_kg": {"ko": "👇 몇 kg 판매할까요?", "en": "👇 How many kg to sell?"},
    "ask_in": {"ko": "👇 몇 개 입고됐나요?", "en": "👇 How many came in?"},
    "ask_in_kg": {"ko": "👇 몇 kg 입고됐나요?", "en": "👇 How many kg came in?"},
    "type_qty": {"ko": "⌨️ <b>{name}</b>\n수량을 숫자로 입력하세요", "en": "⌨️ <b>{name}</b>\nType the quantity"},
    "bad_qty": {"ko": "⚠️ 수량을 숫자로 입력해주세요. (개 단위는 정수만)", "en": "⚠️ Please type a number. (whole numbers for pieces)"},
    "not_enough": {"ko": "⚠️ 재고가 부족해요: <b>{name}</b> (현재 {stock}{unit}, 요청 {qty}{unit})", "en": "⚠️ Not enough stock: <b>{name}</b> (have {stock}{unit}, need {qty}{unit})"},
    "cart_title": {"ko": "🧺 <b>장바구니</b> · {n}개 상품", "en": "🧺 <b>Cart</b> · {n} items"},
    "cart_empty": {"ko": "🧺 장바구니가 비어 있어요.", "en": "🧺 Your cart is empty."},
    "cart_added": {"ko": "✅ <b>{name}</b> {qty}{unit} 담았어요", "en": "✅ Added <b>{name}</b> {qty}{unit}"},
    "total": {"ko": "합계", "en": "Total"},
    "pick_pay": {"ko": "💳 <b>결제수단을 선택하세요</b>", "en": "💳 <b>Choose payment method</b>"},
    "receipt_cap": {"ko": "✅ <b>결제 완료!</b> {total} · {pay}\n🧾 영수증 이미지를 손님께 그대로 전달할 수 있어요.", "en": "✅ <b>Paid!</b> {total} · {pay}\n🧾 Forward this receipt straight to the customer."},
    "receipt_sub": {"ko": "ShopOn POS · 영수증", "en": "ShopOn POS · Receipt"},
    "r_order": {"ko": "주문번호", "en": "Order"},
    "r_date": {"ko": "일시", "en": "Date"},
    "r_pay": {"ko": "결제", "en": "Payment"},
    "r_staff": {"ko": "담당", "en": "Staff"},
    "r_thanks": {"ko": "감사합니다 · Salamat po!", "en": "Thank you · Salamat po!"},
    "alert_title": {"ko": "재고 부족 알림", "en": "Low stock alert"},
    "alert_sub": {"ko": "방금 판매로 최소 재고 이하가 됐어요", "en": "Just dropped to or below minimum"},
    "alert_cap": {"ko": "🚨 <b>재고 부족 알림</b>\n{items}\n\n입고가 필요해요!", "en": "🚨 <b>Low stock alert</b>\n{items}\n\nTime to restock!"},
    "low_title": {"ko": "부족 상품", "en": "Low stock"},
    "low_sub": {"ko": "최소 재고 이하 · 누르면 바로 입고", "en": "At or below minimum · tap to restock"},
    "low_cap": {"ko": "⚠️ <b>부족 상품 {n}개</b> · 번호를 누르면 바로 입고할 수 있어요", "en": "⚠️ <b>{n} items low</b> · tap a number to restock"},
    "low_none": {"ko": "🎉 부족한 상품이 없어요!", "en": "🎉 Nothing is running low!"},
    "in_done": {"ko": "✅ <b>입고 완료</b>\n{line}\n<b>{name}</b>\n➕ {qty}{unit} 입고\n📦 현재 재고  <b>{stock}{unit}</b>", "en": "✅ <b>Stock in done</b>\n{line}\n<b>{name}</b>\n➕ {qty}{unit} received\n📦 Now in stock  <b>{stock}{unit}</b>"},
    "exp_ask_item": {"ko": "💸 <b>지출 기록</b>\n항목을 고르거나 직접 입력하세요", "en": "💸 <b>New expense</b>\nPick or type an item"},
    "exp_ask_amount": {"ko": "💸 <b>{item}</b>\n금액(₱)을 숫자로 입력하세요", "en": "💸 <b>{item}</b>\nType the amount (₱)"},
    "exp_bad_amount": {"ko": "⚠️ 금액을 숫자로 입력해주세요. 예: 1500", "en": "⚠️ Please type a number. e.g. 1500"},
    "exp_pick_pay": {"ko": "💸 <b>{item}</b> · {amount}\n결제수단을 선택하세요", "en": "💸 <b>{item}</b> · {amount}\nChoose payment method"},
    "exp_done": {"ko": "✅ <b>지출 기록 완료</b>\n{line}\n{item}  <b>{amount}</b> ({pay})", "en": "✅ <b>Expense saved</b>\n{line}\n{item}  <b>{amount}</b> ({pay})"},
    "exp_items": {"ko": ["⚡ 전기세", "🚚 운송비", "📦 포장재", "🧽 청소용품", "🍱 식대"],
                  "en": ["⚡ Electricity", "🚚 Delivery", "📦 Packaging", "🧽 Cleaning", "🍱 Meals"]},
    "att_title": {"ko": "👤 <b>출퇴근 기록</b> · 오늘", "en": "👤 <b>Attendance</b> · today"},
    "att_none": {"ko": "아직 기록이 없어요.", "en": "No records yet."},
    "att_in": {"ko": "출근", "en": "in"},
    "att_out": {"ko": "퇴근", "en": "out"},
    "att_done": {"ko": "✅ {name}님 {kind} 완료 ({time})", "en": "✅ {name} clocked {kind} ({time})"},
    "rep_title": {"ko": "오늘 마감 리포트", "en": "Daily Closing Report"},
    "rep_sales": {"ko": "총 매출", "en": "Total sales"},
    "rep_orders": {"ko": "주문", "en": "Orders"},
    "rep_exp": {"ko": "지출", "en": "Expenses"},
    "rep_cash": {"ko": "금고 현금", "en": "Cash drawer"},
    "rep_pay": {"ko": "결제수단", "en": "Payment methods"},
    "rep_top": {"ko": "많이 팔린 상품 TOP 5", "en": "Top 5 products"},
    "rep_empty": {"ko": "아직 판매가 없어요", "en": "No sales yet"},
    "rep_low": {"ko": "⚠ 재고 부족 {n}개 상품", "en": "⚠ {n} items low on stock"},
    "rep_ok": {"ko": "✓ 재고 모두 충분해요", "en": "✓ All stock is fine"},
    "rep_cap": {"ko": "📊 <b>{date} 마감</b>\n💰 매출 <b>{sales}</b> · 주문 {n}건\n💵 금고 현금 = 현금 매출 − 현금 지출", "en": "📊 <b>Closing {date}</b>\n💰 Sales <b>{sales}</b> · {n} orders\n💵 Cash drawer = cash sales − cash expenses"},
    "search_title": {"ko": "검색: {q}", "en": "Search: {q}"},
    "search_sub": {"ko": "{n}개 상품 · 누르면 바로 판매", "en": "{n} products · tap to sell"},
    "search_cap": {"ko": "🔎 '<b>{q}</b>' 검색 결과", "en": "🔎 Results for '<b>{q}</b>'"},
    "search_none": {"ko": "🔎 '<b>{q}</b>' 상품을 찾지 못했어요.", "en": "🔎 No product matches '<b>{q}</b>'."},
    "reset_done": {"ko": "♻️ 데모 데이터를 초기화했어요. (상품 {n}개)", "en": "♻️ Demo data reset. ({n} products)"},
    "no_perm": {"ko": "⛔ 권한이 없어요.", "en": "⛔ Not allowed."},
}

BOT_DESCRIPTION = {
    "ko": ("🛒 {store} 매장관리봇 (ShopOn 데모)\n\n"
           "• 사진 보고 고르는 판매 · 장바구니 · 영수증\n"
           "• 판매하면 재고 자동 차감 + 부족 알림\n"
           "• 입고 · 지출 · 출퇴근 기록\n"
           "• 오늘 마감 리포트를 한 장으로\n\n"
           "아래 [시작] 버튼을 눌러보세요!"),
    "en": ("🛒 {store} store bot (ShopOn demo)\n\n"
           "• Sell from product photos · cart · receipts\n"
           "• Automatic stock deduction + low-stock alerts\n"
           "• Stock in · expenses · attendance\n"
           "• One-page daily closing report\n\n"
           "Tap [Start] below to try it!"),
}
BOT_SHORT = {"ko": "{store} 판매·재고·마감 관리봇 · ShopOn 데모", "en": "{store} sales, stock & closing bot · ShopOn demo"}
COMMANDS = {
    "ko": [("start", "홈 화면"), ("menu", "메뉴 열기"), ("reset", "데모 데이터 초기화")],
    "en": [("start", "Home"), ("menu", "Open menu"), ("reset", "Reset demo data")],
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


def now():
    return datetime.now(TZ)


def today():
    return now().strftime("%Y-%m-%d")


def date_line(lang):
    d = now()
    if lang == "ko":
        return f"{d.year}년 {d.month}월 {d.day}일 ({'월화수목금토일'[d.weekday()]})"
    return d.strftime("%a, %b %d %Y")


def esc(s):
    return html.escape(str(s))


def img_path(name):
    return IMAGE_DIR / name if name else None


def is_low(p):
    return p["stock"] <= p["min_stock"]


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


def low_products():
    return db.execute("SELECT * FROM products WHERE stock <= min_stock ORDER BY stock / MAX(min_stock, 1)").fetchall()


DEMO_STAFF = ["Maria Santos", "Jose Reyes", "Ana Cruz"]


def seed_demo_day():
    """Fills today with a believable morning of trade (sales, two expenses, staff clock-ins)
    the first time today's screens are opened, so the dashboard and report never start empty.
    Stock is left as listed in products.csv so the low-stock examples stay as planned."""
    day = today()
    if db.execute("SELECT 1 FROM sales WHERE day=? LIMIT 1", (day,)).fetchone():
        return
    rnd = random.Random(day)
    prods = db.execute("SELECT * FROM products").fetchall()
    favourites = [p for p in prods if p["category"].split(" ")[0] in ("정육", "음료", "주류", "라면", "생수")]
    start = now().replace(hour=8, minute=30, second=0, microsecond=0)
    if start > now():  # opened before opening time: pretend the shift started three hours ago
        start = now() - timedelta(hours=3)
    span = max(60, int((now() - start).total_seconds() // 60))
    for i, staff in enumerate(DEMO_STAFF[:2]):
        db.execute("INSERT INTO attendance (ts, day, user_id, user_name, kind) VALUES (?,?,?,?,?)",
                   (start.replace(minute=15 + i * 7).isoformat(timespec="seconds"), day, 0, staff, "in"))
    for _ in range(rnd.randint(18, 24)):
        ts = start + timedelta(minutes=rnd.randint(0, span))
        lines = []
        for _ in range(rnd.choice([1, 1, 2, 2, 3, 4])):
            p = rnd.choice(favourites if rnd.random() < 0.7 else prods)
            q = rnd.choice([0.5, 1, 1.5]) if p["unit"] == "kg" else rnd.choice([1, 1, 1, 2, 3])
            lines.append((p, q))
        total = sum(p["price"] * q for p, q in lines)
        pay = rnd.choices(PAY_METHODS, weights=[50, 32, 12, 6])[0]
        cur = db.execute("INSERT INTO sales (ts, day, user_id, user_name, total, payment) VALUES (?,?,?,?,?,?)",
                         (ts.isoformat(timespec="seconds"), day, 0, rnd.choice(DEMO_STAFF[:2]), total, pay))
        db.executemany("INSERT INTO sale_items VALUES (?,?,?,?,?)",
                       [(cur.lastrowid, p["id"], p["name"], q, p["price"]) for p, q in lines])
    for item, amount, pay in (("운송비", 1200, "Cash"), ("포장재", 850, "GCash")):
        db.execute("INSERT INTO expenses (ts, day, user_name, item, amount, payment) VALUES (?,?,?,?,?,?)",
                   ((start + timedelta(minutes=40)).isoformat(timespec="seconds"), day, DEMO_STAFF[0], item, amount, pay))
    db.commit()


def today_totals():
    r = db.execute("SELECT COUNT(*) n, COALESCE(SUM(total), 0) t FROM sales WHERE day=?", (today(),)).fetchone()
    return r["t"], r["n"]


# ---------------------------------------------------------------- per-user state

def lang_of(context):
    return context.user_data.get("lang", "ko")


def cart_of(context):
    return context.user_data.setdefault("cart", {})


def user_name(update):
    u = update.effective_user
    return u.full_name or u.username or str(u.id)


# ---------------------------------------------------------------- pictures

# Rendered images are cached by a key describing their content, and once Telegram has a
# copy its file_id is reused, so an unchanged screen is never drawn or uploaded twice.
_pics = OrderedDict()   # key -> JPEG bytes
_file_ids = {}          # key -> Telegram file_id
_PIC_CACHE_MAX = 300


def pic(kind, render, *parts):
    key = kind + ":" + hashlib.md5(repr(parts).encode()).hexdigest()
    if key in _pics:
        _pics.move_to_end(key)
    else:
        _pics[key] = render()
        while len(_pics) > _PIC_CACHE_MAX:
            old, _ = _pics.popitem(last=False)
            _file_ids.pop(old, None)
    return key


def product_pic(p):
    path = img_path(p["image"])
    if not path or not path.is_file():
        return None
    return pic("img", path.read_bytes, p["image"])


def photo_media(key):
    return _file_ids.get(key) or BytesIO(_pics[key])


def remember_photo(key, msg):
    photos = getattr(msg, "photo", None)
    if photos:
        _file_ids[key] = photos[-1].file_id


# ---------------------------------------------------------------- screens
# Each screen returns (caption, keyboard, picture key or None).

def home_row(lang):
    return [Btn(tr("btn_home", lang), callback_data="m:home")]


def home_screen(lang, context, caption=None):
    seed_demo_day()
    sales, orders = today_totals()
    low = len(low_products())
    stats = [(tr("stat_sales", lang), money(sales), False),
             (tr("stat_orders", lang), tr("n_orders", lang, n=orders), False),
             (tr("stat_low", lang), tr("n_items", lang, n=low), low > 0)]
    args = (str(IMAGE_DIR / "store.jpg"), tr("home_eyebrow", lang), STORE_NAME, tr("home_tag", lang),
            date_line(lang), stats)
    key = pic("home", lambda: cards.home(*args), args)
    rows = [[Btn(tr("btn_sell", lang), callback_data="m:sell")]]
    n = len(cart_of(context))
    if n:
        rows.append([Btn(tr("btn_cart", lang, n=n), callback_data="k:view")])
    rows += [
        [Btn(tr("btn_stock", lang), callback_data="m:stock"), Btn(tr("btn_in", lang), callback_data="m:in")],
        [Btn(tr("btn_exp", lang), callback_data="m:exp"), Btn(tr("btn_att", lang), callback_data="m:att")],
        [Btn(tr("btn_close", lang), callback_data="m:close")],
        [Btn(tr("btn_lang", lang), callback_data="m:lang")],
    ]
    return caption or tr("menu", lang), Kb(rows), key


def grid_pic(title, subtitle, tiles, accent=cards.GREEN):
    return pic("grid", lambda: cards.grid(title, subtitle, tiles, accent), title, subtitle, tiles, accent)


def product_tile(n, p, lang):
    u = unit_label(p["unit"], lang)
    price = money(p["price"]) + ("/kg" if p["unit"] == "kg" else "")
    stock = f"{qty_str(p['stock'])}{u}"
    return dict(img=str(img_path(p["image"])), num=n, name=p["name"], left=price,
                pill=tr("pill_low", lang, q=stock) if is_low(p) else stock, low=is_low(p))


def category_screen(mode, lang):
    """mode: s = sell, i = stock in, v = view stock."""
    rows, row, tiles = [], [], []
    for ci, cat in enumerate(categories()):
        prods = products_in(cat)
        low = sum(1 for p in prods if is_low(p))
        tiles.append(dict(img=str(img_path(prods[0]["image"])), num=ci + 1, name=cat_label(cat, lang),
                          left=tr("cat_count", lang, n=len(prods)),
                          pill=tr("cat_low", lang, n=low) if (low and mode == "v") else None, low=low > 0 and mode == "v"))
        label = f"{ci + 1}. {cat_label(cat, lang)}" + (f" 🔴{low}" if low and mode == "v" else "")
        row.append(Btn(label, callback_data=f"c:{mode}:{ci}:0"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if mode == "v":
        rows.append([Btn(tr("btn_low", lang), callback_data="v:low")])
    rows.append(home_row(lang))
    name = {"s": "sell", "i": "in", "v": "stock"}[mode]
    key = grid_pic(tr(f"grid_cats_{name}", lang), tr("grid_cats_sub", lang), tiles)
    return tr(f"cap_cats_{name}", lang), Kb(rows), key


def product_list_screen(mode, ci, page, lang, context):
    cats = categories()
    if ci >= len(cats):
        return category_screen(mode, lang)
    cat = cats[ci]
    prods = products_in(cat)
    pages = max(1, (len(prods) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(page, 0), pages - 1)
    # From the stock view, tapping a product goes straight to restocking it.
    target = "i" if mode == "v" else mode
    rows, tiles = [], []
    for n, p in enumerate(prods[page * PAGE_SIZE:(page + 1) * PAGE_SIZE], 1):
        tiles.append(product_tile(n, p, lang))
        label = f"{n}. {p['name']} · {money(p['price'])}"
        if mode == "v":
            label = f"{n}. {p['name']} · {qty_str(p['stock'])}{unit_label(p['unit'], lang)}"
        rows.append([Btn(("🔴 " if is_low(p) else "") + label, callback_data=f"p:{target}:{p['id']}")])
    nav = []
    if page > 0:
        nav.append(Btn("⬅", callback_data=f"c:{mode}:{ci}:{page - 1}"))
    if page < pages - 1:
        nav.append(Btn("➡", callback_data=f"c:{mode}:{ci}:{page + 1}"))
    if nav:
        rows.append(nav)
    if mode == "s" and cart_of(context):
        rows.append([Btn(tr("btn_cart", lang, n=len(cart_of(context))), callback_data="k:view")])
    rows.append([Btn(tr("btn_back", lang), callback_data={"s": "m:sell", "i": "m:in", "v": "m:stock"}[mode]),
                 *home_row(lang)])
    sub = tr("grid_stock_sub" if mode == "v" else "grid_prod_sub", lang, page=page + 1, pages=pages)
    key = grid_pic(cat_label(cat, lang), sub, tiles)
    return tr("cap_prod", lang, cat=esc(cat_label(cat, lang))), Kb(rows), key


def product_card(mode, p, lang):
    u = unit_label(p["unit"], lang)
    kg = p["unit"] == "kg"
    ask = tr(("ask_sell" if mode == "s" else "ask_in") + ("_kg" if kg else ""), lang)
    text = tr("card", lang, name=esc(p["name"]), price=money(p["price"]), unit=u, stock=qty_str(p["stock"]),
              low=tr("card_low", lang) if is_low(p) else "", ask=ask, line=LINE)
    qtys = QTY_KG if kg else QTY_EA
    rows = [[Btn(qty_str(q), callback_data=f"q:{mode}:{p['id']}:{q}") for q in qtys],
            [Btn(tr("btn_type", lang), callback_data=f"x:{mode}:{p['id']}")]]
    cats = categories()
    ci = cats.index(p["category"]) if p["category"] in cats else 0
    rows.append([Btn(tr("btn_back", lang), callback_data=f"c:{mode}:{ci}:0"), *home_row(lang)])
    return text, Kb(rows), product_pic(p)


def cart_screen(lang, context, note=None):
    cart = cart_of(context)
    if not cart:
        text = tr("cart_empty", lang)
        return (f"{note}\n\n{text}" if note else text), Kb([[Btn(tr("btn_sell", lang), callback_data="m:sell")],
                                                           home_row(lang)]), None
    lines, total = [tr("cart_title", lang, n=len(cart)), LINE], 0
    for pid, q in cart.items():
        p = product(int(pid))
        sub = p["price"] * q
        total += sub
        lines.append(f"<b>{esc(p['name'])}</b>\n     {qty_str(q)}{unit_label(p['unit'], lang)} × {money(p['price'])}"
                     f" = <b>{money(sub)}</b>")
    lines += [LINE, f"💰 {tr('total', lang)}  <b>{money(total)}</b>"]
    if note:
        lines.insert(0, note + "\n")
    rows = [[Btn(tr("btn_pay", lang), callback_data="k:pay")],
            [Btn(tr("btn_more", lang), callback_data="m:sell"), Btn(tr("btn_clear", lang), callback_data="k:clear")],
            home_row(lang)]
    return "\n".join(lines), Kb(rows), None


def attendance_screen(lang, note=None):
    recs = db.execute("SELECT * FROM attendance WHERE day=? ORDER BY id", (today(),)).fetchall()
    lines = [tr("att_title", lang), LINE]
    if not recs:
        lines.append(tr("att_none", lang))
    for r in recs:
        icon = "🟢" if r["kind"] == "in" else "🔴"
        lines.append(f"{icon} {r['ts'][11:16]}  {esc(r['user_name'])} · {tr('att_' + r['kind'], lang)}")
    if note:
        lines.insert(0, note + "\n")
    rows = [[Btn(tr("btn_in_ok", lang), callback_data="a:in"), Btn(tr("btn_out_ok", lang), callback_data="a:out")],
            home_row(lang)]
    return "\n".join(lines), Kb(rows), None


def low_screen(lang):
    low = low_products()[:12]
    if not low:
        return tr("low_none", lang), Kb([[Btn(tr("btn_back", lang), callback_data="m:stock"), *home_row(lang)]]), None
    tiles = [product_tile(n, p, lang) for n, p in enumerate(low, 1)]
    rows = [[Btn(f"🔴 {n}. {p['name']} · {qty_str(p['stock'])}{unit_label(p['unit'], lang)}",
                 callback_data=f"p:i:{p['id']}")] for n, p in enumerate(low, 1)]
    rows.append([Btn(tr("btn_back", lang), callback_data="m:stock"), *home_row(lang)])
    key = grid_pic(tr("low_title", lang), tr("low_sub", lang), tiles, cards.RED)
    return tr("low_cap", lang, n=len(low_products())), Kb(rows), key


def report_screen(lang):
    seed_demo_day()
    day = today()
    sales = db.execute("SELECT payment, COUNT(*) n, SUM(total) t FROM sales WHERE day=? GROUP BY payment "
                       "ORDER BY t DESC", (day,)).fetchall()
    total = sum(r["t"] for r in sales)
    count = sum(r["n"] for r in sales)
    top = db.execute("""
        SELECT si.name, SUM(si.qty * si.unit_price) amt FROM sale_items si
        JOIN sales s ON s.id = si.sale_id WHERE s.day=? GROUP BY si.product_id ORDER BY amt DESC LIMIT 5""",
                     (day,)).fetchall()
    exps = db.execute("SELECT payment, SUM(amount) a FROM expenses WHERE day=? GROUP BY payment", (day,)).fetchall()
    exp_total = sum(r["a"] for r in exps)
    cash = sum(r["t"] for r in sales if r["payment"] == "Cash") - sum(r["a"] for r in exps if r["payment"] == "Cash")
    n_low = len(low_products())

    kpis = [(tr("rep_sales", lang), money(total), cards.INK),
            (tr("rep_orders", lang), tr("n_orders", lang, n=count), cards.INK),
            (tr("rep_exp", lang), money(exp_total), cards.RED if exp_total else cards.INK),
            (tr("rep_cash", lang), money(cash), cards.GREEN if cash >= 0 else cards.RED)]
    pays = [(r["payment"], money(r["t"]), r["t"] / total) for r in sales] if total else []
    best = top[0]["amt"] if top else 1
    tops = [(r["name"], money(r["amt"]), r["amt"] / best) for r in top]
    foot = tr("rep_low", lang, n=n_low) if n_low else tr("rep_ok", lang)
    args = (tr("rep_title", lang), date_line(lang), kpis, tr("rep_pay", lang), pays, tr("rep_top", lang), tops,
            tr("rep_empty", lang), foot, n_low > 0)
    key = pic("report", lambda: cards.report(*args), args)
    rows = [[Btn(tr("btn_low", lang), callback_data="v:low")]] if n_low else []
    rows.append(home_row(lang))
    return tr("rep_cap", lang, date=day, sales=money(total), n=count), Kb(rows), key


# ---------------------------------------------------------------- message helpers

async def show(query, text, kb, photo=None):
    """Replace the tapped message with the next screen. Photo-to-photo is edited in place;
    a photo message can't become text (or the reverse), so those are deleted and re-sent."""
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
        await send_screen(msg.chat, text, kb, photo)
        return
    if msg.photo:
        await remove(msg)
        await send_screen(msg.chat, text, kb)
        return
    try:
        await msg.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


async def send_screen(chat, text, kb=None, photo=None):
    if photo:
        sent = await chat.send_photo(photo_media(photo), caption=text, reply_markup=kb, parse_mode="HTML")
        remember_photo(photo, sent)
        return sent
    return await chat.send_message(text, reply_markup=kb, parse_mode="HTML")


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


def apply_qty(update, context, mode, pid, q):
    """Adds to the cart (sell) or records a delivery (stock in); returns the next screen."""
    lang = lang_of(context)
    p = product(pid)
    if p is None:
        return home_screen(lang, context)
    u = unit_label(p["unit"], lang)
    if mode == "s":
        err = add_to_cart(context, p, q, lang)
        note = err or tr("cart_added", lang, name=esc(p["name"]), qty=qty_str(q), unit=u)
        return cart_screen(lang, context, note)
    db.execute("UPDATE products SET stock = stock + ? WHERE id=?", (q, p["id"]))
    db.execute("INSERT INTO stock_in (ts, day, user_name, product_id, qty) VALUES (?,?,?,?,?)",
               (now().isoformat(timespec="seconds"), today(), user_name(update), p["id"], q))
    db.commit()
    p = product(p["id"])
    cats = categories()
    ci = cats.index(p["category"]) if p["category"] in cats else 0
    kb = Kb([[Btn(tr("btn_in", lang), callback_data=f"c:i:{ci}:0"), *home_row(lang)]])
    text = tr("in_done", lang, name=esc(p["name"]), qty=qty_str(q), unit=u, stock=qty_str(p["stock"]), line=LINE)
    return text, kb, product_pic(p)


async def checkout(update, context, query, method):
    lang = lang_of(context)
    cart = cart_of(context)
    if not cart:
        await show(query, *cart_screen(lang, context))
        return
    items = [(product(int(pid)), q) for pid, q in cart.items()]
    for p, q in items:
        if q > p["stock"]:
            err = tr("not_enough", lang, name=esc(p["name"]), stock=qty_str(p["stock"]), qty=qty_str(q),
                     unit=unit_label(p["unit"], lang))
            await show(query, *cart_screen(lang, context, err))
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

    lines = [(p["name"], f"{qty_str(q)}{unit_label(p['unit'], lang)} × {money(p['price'])}", money(p["price"] * q))
             for p, q in items]
    args = (STORE_NAME, tr("receipt_sub", lang),
            [(tr("r_order", lang), f"#{sid:04d}"), (tr("r_date", lang), ts.strftime("%Y-%m-%d %H:%M"))],
            lines, tr("total", lang), money(total),
            [(tr("r_pay", lang), method), (tr("r_staff", lang), user_name(update))], tr("r_thanks", lang))
    key = pic("receipt", lambda: cards.receipt(*args, seed=sid), args, sid)
    kb = Kb([[Btn(tr("btn_sell", lang), callback_data="m:sell")], home_row(lang)])
    await show(query, tr("receipt_cap", lang, total=money(total), pay=method), kb, key)

    # Alert on anything this sale pushed to or below its minimum.
    low = [product(p["id"]) for p, _ in items]
    low = [p for p in low if is_low(p)]
    if low:
        tiles = [product_tile(n, p, lang) for n, p in enumerate(low[:8], 1)]
        alert_key = grid_pic(tr("alert_title", lang), tr("alert_sub", lang), tiles, cards.RED)
        names = "\n".join(f"🔴 {esc(p['name'])} · <b>{qty_str(p['stock'])}{unit_label(p['unit'], lang)}</b>"
                          for p in low)
        caption = tr("alert_cap", lang, items=names)
        kb = Kb([[Btn(tr("btn_restock", lang), callback_data=f"p:i:{low[0]['id']}")]])
        await send_screen(query.message.chat, caption, kb, alert_key)
        if ALERT_CHAT_ID and str(ALERT_CHAT_ID) != str(query.message.chat.id):
            try:
                await context.bot.send_photo(ALERT_CHAT_ID, photo_media(alert_key), caption=caption, parse_mode="HTML")
            except Exception:
                log.exception("Could not send low-stock alert to ALERT_CHAT_ID")


# ---------------------------------------------------------------- handlers

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    context.user_data.pop("await", None)
    welcome = tr("welcome", lang, store=esc(STORE_NAME))
    await send_screen(update.effective_chat, *home_screen(lang, context, caption=welcome))


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("await", None)
    await send_screen(update.effective_chat, *home_screen(lang_of(context), context))


async def cmd_chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message(f"chat id: <code>{update.effective_chat.id}</code>", parse_mode="HTML")


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.effective_chat.send_message(tr("no_perm", lang))
        return
    n = init_db(reset=True)
    context.user_data["cart"] = {}
    await send_screen(update.effective_chat, *home_screen(lang, context, caption=tr("reset_done", lang, n=n)))


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = lang_of(context)
    parts = query.data.split(":")
    kind = parts[0]
    context.user_data.pop("await", None)

    if kind == "m":
        what = parts[1]
        if what == "lang":
            context.user_data["lang"] = lang = "en" if lang == "ko" else "ko"
            await show(query, *home_screen(lang, context))
        elif what == "home":
            await show(query, *home_screen(lang, context))
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
            await show(query, *report_screen(lang))

    elif kind == "c":
        mode, ci, page = parts[1], int(parts[2]), int(parts[3])
        await show(query, *product_list_screen(mode, ci, page, lang, context))

    elif kind == "p":
        p = product(int(parts[2]))
        if p:
            await show(query, *product_card(parts[1], p, lang))

    elif kind == "q":
        mode, pid, q = parts[1], int(parts[2]), float(parts[3])
        await show(query, *apply_qty(update, context, mode, pid, q))

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
            text, _, _ = cart_screen(lang, context)
            rows = [[Btn(m, callback_data=f"y:{m}") for m in PAY_METHODS[:2]],
                    [Btn(m, callback_data=f"y:{m}") for m in PAY_METHODS[2:]],
                    [Btn(tr("btn_back", lang), callback_data="k:view")]]
            await show(query, f"{text}\n\n{tr('pick_pay', lang)}", Kb(rows))

    elif kind == "y":
        await checkout(update, context, query, parts[1])

    elif kind == "v" and parts[1] == "low":
        await show(query, *low_screen(lang))

    elif kind == "ei":
        item = tr("exp_items", lang)[int(parts[1])].split(" ", 1)[-1]
        context.user_data["await"] = ("exp_amount", item)
        await show(query, tr("exp_ask_amount", lang, item=esc(item)), Kb([home_row(lang)]))

    elif kind == "e":
        pending = context.user_data.pop("exp_pending", None)
        if not pending:
            await show(query, *home_screen(lang, context))
            return
        item, amount = pending
        db.execute("INSERT INTO expenses (ts, day, user_name, item, amount, payment) VALUES (?,?,?,?,?,?)",
                   (now().isoformat(timespec="seconds"), today(), user_name(update), item, amount, parts[1]))
        db.commit()
        await show(query, tr("exp_done", lang, item=esc(item), amount=money(amount), pay=parts[1], line=LINE),
                   Kb([[Btn(tr("btn_exp", lang), callback_data="m:exp"), *home_row(lang)]]))

    elif kind == "a":
        ts = now()
        db.execute("INSERT INTO attendance (ts, day, user_id, user_name, kind) VALUES (?,?,?,?,?)",
                   (ts.isoformat(timespec="seconds"), today(), update.effective_user.id, user_name(update), parts[1]))
        db.commit()
        done = tr("att_done", lang, name=esc(user_name(update)), kind=tr("att_" + parts[1], lang),
                  time=ts.strftime("%H:%M"))
        await show(query, *attendance_screen(lang, done))


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
        await send_screen(chat, *apply_qty(update, context, mode, pid, q))
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
        rows = [[Btn(m, callback_data=f"e:{m}") for m in PAY_METHODS[:2]],
                [Btn(m, callback_data=f"e:{m}") for m in PAY_METHODS[2:]], home_row(lang)]
        await chat.send_message(tr("exp_pick_pay", lang, item=esc(item), amount=money(amount)),
                                reply_markup=Kb(rows), parse_mode="HTML")
        return

    # Anything else is treated as a product search that leads straight into a sale.
    hits = db.execute("SELECT * FROM products WHERE name LIKE ? ORDER BY id LIMIT 12", (f"%{text}%",)).fetchall()
    if not hits:
        _, kb, _ = home_screen(lang, context)
        await chat.send_message(tr("search_none", lang, q=esc(text)), reply_markup=kb, parse_mode="HTML")
        return
    rows = [[Btn(("🔴 " if is_low(p) else "") + f"{n}. {p['name']} · {money(p['price'])}", callback_data=f"p:s:{p['id']}")]
            for n, p in enumerate(hits, 1)]
    rows.append(home_row(lang))
    tiles = [product_tile(n, p, lang) for n, p in enumerate(hits, 1)]
    key = grid_pic(tr("search_title", lang, q=text[:20]), tr("search_sub", lang, n=len(hits)), tiles)
    await send_screen(chat, tr("search_cap", lang, q=esc(text)), Kb(rows), key)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error("Unhandled error", exc_info=context.error)


async def post_init(app):
    """Fills in the bot's profile text and / command menu, so the empty chat already looks finished."""
    for lang, code in (("ko", None), ("en", "en")):
        try:
            await app.bot.set_my_commands([BotCommand(c, d) for c, d in COMMANDS[lang]], language_code=code)
            await app.bot.set_my_description(BOT_DESCRIPTION[lang].format(store=STORE_NAME), language_code=code)
            await app.bot.set_my_short_description(BOT_SHORT[lang].format(store=STORE_NAME), language_code=code)
        except Exception as e:
            log.warning("Could not set bot profile (%s): %s", lang, e)


def build_app():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
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
