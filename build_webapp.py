"""Writes docs/products.json for the mini app from products.csv.

The mini app (docs/index.html) is a static page served by GitHub Pages, so it reads the
catalogue from this file; live stock is passed by the bot in the page URL instead.
Run after editing products.csv:  python build_webapp.py
"""
import csv
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent

with open(BASE / "products.csv", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

cats = []
for r in rows:
    if r["category"] not in cats:
        cats.append(r["category"])

data = {
    "categories": [{"ko": c.partition(" ")[0], "en": c.partition(" ")[2] or c} for c in cats],
    "products": [{"id": int(r["id"]), "c": cats.index(r["category"]), "n": r["name"], "p": float(r["price"]),
                  "u": r["unit"], "min": float(r["min_stock"]), "img": r["image"]}
                 for r in sorted(rows, key=lambda r: int(r["id"]))],
}
(BASE / "docs").mkdir(exist_ok=True)
(BASE / "docs" / "products.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"docs/products.json: {len(data['products'])} products, {len(cats)} categories")
