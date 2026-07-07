"""Scrape biklo.at — AT/CZ listings from __NEXT_DATA__."""
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

from filters import CZK_PER_EUR, PRICE_EUR_MAX, PRICE_EUR_MIN, czk_to_eur

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "biklo_listings.json"
BASE = "https://www.biklo.at"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}

PAGES = [
    ("AT", f"{BASE}/markt/austria-country-filter"),
    ("CZ", f"{BASE}/markt/czech-republic-country-filter"),
    ("AT", f"{BASE}/markt/fahrrader-1/mtb-enduro-trail-1"),
    ("AT", f"{BASE}/markt/fahrrader-1/mtb-cross-country/full-suspension-de"),
]


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as r:
        html = r.read().decode("utf-8", errors="replace")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return {}
    return json.loads(m.group(1))


def posts_from(nd: dict) -> list[dict]:
    try:
        return nd["props"]["pageProps"]["initialState"]["PageStore"]["page_wrapper"]["posts"]["data"]
    except (KeyError, TypeError):
        return []


def image_url(pictures: list | None) -> str | None:
    if not pictures:
        return None
    fn = pictures[0].get("filename") if isinstance(pictures[0], dict) else None
    if not fn:
        return None
    if fn.startswith("http"):
        return fn
    return f"{BASE}/{fn.lstrip('/')}"


def price_eur(post: dict, region_hint: str) -> float | None:
    raw = post.get("price")
    if raw is None:
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    cc = (post.get("country_code") or region_hint or "").upper()
    if cc == "CZ":
        return czk_to_eur(val)
    return val


def normalize(post: dict, region_hint: str) -> dict | None:
    pe = price_eur(post, region_hint)
    if pe is None or pe < PRICE_EUR_MIN or pe > PRICE_EUR_MAX:
        return None
    cc = (post.get("country_code") or region_hint or "AT").upper()
    city = (post.get("city") or {}).get("name", "")
    slug = post.get("slug") or str(post.get("id"))
    source = "biklo.cz" if cc == "CZ" else "biklo.at"
    loc = f"{city}, {cc}" if city else cc
    return {
        "id": str(post.get("id") or slug),
        "source": source,
        "title": (post.get("title") or "").strip(),
        "description": (post.get("description") or "").strip()[:2000],
        "price_eur": round(pe, 0),
        "price_czk": round(pe * CZK_PER_EUR) if cc == "CZ" else None,
        "location": loc,
        "url": f"{BASE}/markt/angebot/{slug}",
        "image_url": image_url(post.get("pictures")),
    }


def main() -> None:
    all_items: dict[str, dict] = {}
    for region, url in PAGES:
        print(f"fetch {url}")
        try:
            nd = fetch(url)
        except Exception as e:
            print(f"  fail: {e}")
            continue
        batch = posts_from(nd)
        kept = 0
        for post in batch:
            item = normalize(post, region)
            if not item:
                continue
            cc = (post.get("country_code") or region).upper()
            if region == "AT" and cc not in ("AT", ""):
                continue
            if region == "CZ" and cc not in ("CZ", ""):
                continue
            all_items[item["url"]] = item
            kept += 1
        print(f"  posts={len(batch)} in_budget={kept}")
        time.sleep(0.4)

    items = list(all_items.values())
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(items)} -> {OUT}")


if __name__ == "__main__":
    main()
