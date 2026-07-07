"""Scrape radlmarkt.at — Austrian bike marketplace (niche)."""
from __future__ import annotations

import json
import re
import time
import urllib.request
from html import unescape
from pathlib import Path

from filters import PRICE_EUR_MAX, PRICE_EUR_MIN

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "radlmarkt_listings.json"
BASE = "https://www.radlmarkt.at"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}

LIST_PATHS = [
    "/anzeigen/fahrrader/",
    "/anzeigen/e-bikes/",
]
MAX_PAGES = 3


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as r:
        return unescape(r.read().decode("utf-8", errors="replace"))


def parse_eur_price(raw: str) -> float | None:
    raw = raw.replace("\xa0", " ").replace("€", "").strip()
    if not raw:
        return None
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        whole, frac = raw.split(",", 1)
        raw = whole.replace(".", "") + "." + frac if len(frac) <= 2 else raw.replace(",", "")
    elif "." in raw:
        whole, frac = raw.split(".", 1)
        if frac.isdigit() and len(frac) == 3:
            raw = whole + frac
    try:
        return float(re.sub(r"[^\d.]", "", raw) or 0)
    except ValueError:
        return None


def parse_list_page(html: str) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for m in re.finditer(
        r'<a\s[^>]*class="listivo-listing-card-row-v2"[^>]*href="(https://www\.radlmarkt\.at/anzeige/([^"]+))"',
        html,
        re.I | re.DOTALL,
    ):
        url, slug = m.groups()
        if slug in seen:
            continue
        end = html.find("</a>", m.end())
        block = html[m.start() : end + 4] if end > 0 else html[m.start() : m.start() + 12000]
        title_m = re.search(
            r'listivo-listing-card-name-selector[^>]*>\s*([^<]+?)\s*</h3>',
            block,
            re.I,
        )
        price_m = re.search(
            r'listivo-listing-card-value-selector[^>]*>\s*([^<]+?)\s*</div>',
            block,
            re.I,
        )
        loc_m = re.search(
            r'listivo-listing-card-location-selector[^>]*>\s*([^<]+?)\s*</div>',
            block,
            re.I,
        )
        img_m = re.search(r'<img[^>]+src="(https://[^"]+)"', block)
        desc_m = re.search(
            r'listivo-listing-card-description-selector[^>]*>\s*(.*?)\s*</div>',
            block,
            re.DOTALL | re.I,
        )
        price = parse_eur_price(price_m.group(1)) if price_m else None
        if price is None or price < PRICE_EUR_MIN or price > PRICE_EUR_MAX:
            continue
        desc = re.sub(r"<[^>]+>", " ", desc_m.group(1)) if desc_m else ""
        desc = re.sub(r"\s+", " ", desc).strip()
        seen.add(slug)
        items.append({
            "id": slug.rstrip("/"),
            "source": "radlmarkt.at",
            "title": re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else slug,
            "description": desc[:2000],
            "price_eur": price,
            "location": loc_m.group(1).strip() if loc_m else "Österreich",
            "url": url,
            "image_url": img_m.group(1) if img_m else None,
        })
    return items


def main() -> None:
    all_items: dict[str, dict] = {}
    for path in LIST_PATHS:
        for page in range(1, MAX_PAGES + 1):
            url = f"{BASE}{path}" if page == 1 else f"{BASE}{path}page/{page}/"
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
                all_items[it["id"]] = it
            time.sleep(0.35)

    items = list(all_items.values())
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(items)} -> {OUT}")


if __name__ == "__main__":
    main()
