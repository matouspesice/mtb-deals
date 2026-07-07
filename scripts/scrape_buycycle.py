"""Scrape Buycycle MTB listings from Next.js RSC payload."""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from filters import PRICE_EUR_MAX, PRICE_EUR_MIN
from image_urls import buycycle_image_from_blob

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "buycycle_listings.json"

LOCALES = ["en-at", "en-cz", "en-de"]
BASE = "https://www.buycycle.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def human_title_from_slug(slug: str) -> str:
    slug = re.sub(r"-\d{4,}$", "", slug)
    slug = re.sub(r"-20\d{2}-.*$", "", slug)
    slug = re.sub(r"-gr-[a-z0-9]+-.*$", "", slug, flags=re.I)
    parts = [p for p in slug.split("-") if p and not p.isdigit()]
    return " ".join(parts).title()


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", errors="replace")


def rsc_blob(html: str) -> str:
    parts = re.findall(r'self\.__next_f\.push\(\[1,"((?:\\.|[^"])*)"\]\)', html)
    blob = ""
    for part in parts:
        try:
            blob += bytes(part, "utf-8").decode("unicode_escape")
        except Exception:
            blob += part
    return blob


def parse_listings_from_blob(blob: str, locale: str) -> list[dict]:
    items: list[dict] = []
    # Objects often appear as slug + price + brand nearby in array structure
    slugs = re.findall(r'"slug":"([^"]+)"', blob)
    prices = re.findall(r'"price":(\d+)', blob)
    # Also try paired extraction from product-like blocks
    for m in re.finditer(
        r'"slug":"([^"]+)".{0,400}?"price":(\d+)',
        blob,
        re.DOTALL,
    ):
        slug, price = m.groups()
        price_eur = float(price)
        if not (PRICE_EUR_MIN <= price_eur <= PRICE_EUR_MAX):
            continue
        title = human_title_from_slug(slug)
        year_m = re.search(r"(20\d{2})", slug)
        size_hint = ""
        if msize := re.search(r"-gr-([mlxs\d]+)-", slug):
            size_hint = f" size {msize.group(1).upper()}"
        items.append({
            "id": slug,
            "source": f"buycycle.com ({locale})",
            "title": title,
            "description": slug + size_hint,
            "price_eur": price_eur,
            "year": int(year_m.group(1)) if year_m else None,
            "location": locale.split("-")[-1].upper(),
            "url": f"{BASE}/{locale}/product/{slug}",
            "image_url": buycycle_image_from_blob(blob, slug),
        })

    # fallback: zip slugs and prices if same count
    if not items and slugs and len(slugs) == len(prices):
        for slug, price in zip(slugs, prices):
            price_eur = float(price)
            if PRICE_EUR_MIN <= price_eur <= PRICE_EUR_MAX:
                year_m = re.search(r"(20\d{2})", slug)
                items.append({
                    "id": slug,
                    "source": f"buycycle.com ({locale})",
                    "title": slug.replace("-", " ").title(),
                    "description": slug,
                    "price_eur": price_eur,
                    "year": int(year_m.group(1)) if year_m else None,
                    "location": locale.split("-")[-1].upper(),
                    "url": f"{BASE}/{locale}/product/{slug}",
                    "image_url": buycycle_image_from_blob(blob, slug),
                })
    return items


def fetch_detail(item: dict) -> None:
    try:
        html = fetch(item["url"])
        blob = rsc_blob(html)
        # frame size, travel, description snippets
        for key in ("frame-size", "frame_size", "travel", "suspension", "groupset", "description"):
            m = re.search(rf'"{key}":"([^"]+)"', blob, re.I)
            if m:
                item["description"] += f" {key}:{m.group(1)}"
        m = re.search(r'"modelName":"([^"]+)"', blob)
        if m:
            item["title"] = m.group(1)
        m = re.search(r'"brand":"([^"]+)"', blob)
        if m and m.group(1) not in ("Brand",):
            item["title"] = f"{m.group(1)} {item['title']}"
    except Exception:
        pass


def main() -> None:
    all_items: dict[str, dict] = {}
    params = urllib.parse.urlencode({"max_price": str(PRICE_EUR_MAX)})

    for locale in LOCALES:
        url = f"{BASE}/{locale}/shop/main-types/bikes/types/mountainbike?{params}"
        print(f"Fetching {locale}...")
        try:
            html = fetch(url)
            blob = rsc_blob(html)
            batch = parse_listings_from_blob(blob, locale)
            print(f"  {len(batch)} in price range")
            for it in batch:
                all_items[it["id"]] = it
            time.sleep(0.5)
        except Exception as e:
            print(f"  fail: {e}")

    items = list(all_items.values())
    print(f"Fetching details for {len(items)}...")
    for i, it in enumerate(items, 1):
        fetch_detail(it)
        if i % 30 == 0:
            print(f"  {i}/{len(items)}")
        time.sleep(0.12)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(items)} -> {OUT}")


if __name__ == "__main__":
    main()
