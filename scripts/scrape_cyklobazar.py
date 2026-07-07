"""Scrape cyklobazar.cz — celoodpružená / trail kola."""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from filters import CZK_PER_EUR, PRICE_EUR_MAX, PRICE_EUR_MIN, eur_to_czk

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "cyklobazar_listings.json"
BASE = "https://www.cyklobazar.cz"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}

CATEGORIES = [
    "celoodpruzena-kola",
    "enduro-kola",
]
CENA_OD = eur_to_czk(PRICE_EUR_MIN)
CENA_DO = eur_to_czk(PRICE_EUR_MAX)
MAX_PAGES = 12
FETCH_DETAILS = True
DETAIL_DELAY = 0.2


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_price_czk(block: str) -> float | None:
    m = re.search(r"cb-offer__price[^>]*>\s*([\d\s&nbsp;]+)", block)
    if not m:
        m = re.search(r"([\d\s]{2,})\s*(?:&nbsp;)?\s*(?:<small>)?Kč", block)
    if not m:
        return None
    raw = re.sub(r"[^\d]", "", m.group(1).replace("&nbsp;", " "))
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def parse_list_page(html: str) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for m in re.finditer(r'<a href="(/inzerat/[^"]+)"[^>]*class="[^"]*cb-offer', html):
        path = m.group(1)
        if path in seen:
            continue
        block = html[m.start() : m.start() + 3500]
        if "cb-offer--compact" in block[:200]:
            continue
        seen.add(path)
        title_m = re.search(r"<h4>\s*([^<]+?)\s*</h4>", block)
        loc_m = re.search(r"cb-offer__location[^>]*>\s*([^<]+)", block)
        img_m = re.search(r'<img src="(/uploads/[^"]+)"', block)
        price = parse_price_czk(block)
        if price is None or price < CENA_OD or price > CENA_DO:
            continue
        slug = path.rsplit("/", 1)[-1]
        oid = path.split("/")[2] if path.count("/") >= 2 else slug
        items.append({
            "id": oid,
            "source": "cyklobazar.cz",
            "title": (title_m.group(1) if title_m else slug).strip(),
            "description": "",
            "price_czk": price,
            "price_eur": round(price / CZK_PER_EUR, 0),
            "location": loc_m.group(1).strip() if loc_m else "",
            "url": BASE + path,
            "image_url": BASE + img_m.group(1) if img_m else None,
        })
    return items


def fetch_detail(item: dict) -> str:
    try:
        html = fetch(item["url"])
        m = re.search(r'<div class="[^"]*popis[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL | re.I)
        if not m:
            m = re.search(r'<meta name="description" content="([^"]+)"', html)
            return re.sub(r"\s+", " ", m.group(1)).strip()[:2000] if m else ""
        text = re.sub(r"<[^>]+>", " ", m.group(1))
        return re.sub(r"\s+", " ", text).strip()[:2000]
    except Exception as e:
        print(f"    detail fail {item['id']}: {e}")
    return ""


def main() -> None:
    all_items: dict[str, dict] = {}
    for cat in CATEGORIES:
        for page in range(1, MAX_PAGES + 1):
            params = urllib.parse.urlencode({
                "cena_od": CENA_OD,
                "cena_do": CENA_DO,
                "vp-page": page,
            })
            url = f"{BASE}/{cat}?{params}"
            print(f"fetch {url}")
            try:
                html = fetch(url)
            except Exception as e:
                print(f"  fail: {e}")
                break
            batch = parse_list_page(html)
            print(f"  page {page}: {len(batch)} in budget")
            if not batch:
                break
            for it in batch:
                all_items[it["url"]] = it
            time.sleep(0.35)

    items = list(all_items.values())
    if FETCH_DETAILS:
        for i, it in enumerate(items):
            print(f"detail {i+1}/{len(items)} {it['title'][:40]}")
            it["description"] = fetch_detail(it)
            time.sleep(DETAIL_DELAY)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(items)} -> {OUT}")


if __name__ == "__main__":
    main()
