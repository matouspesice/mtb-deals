"""Scrape sbazar.cz search results — Astro SSR serialized offers."""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path

from filters import CZK_PER_EUR, PRICE_EUR_MAX, PRICE_EUR_MIN, eur_to_czk
from image_urls import sbazar_image_from_chunk

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "sbazar_listings.json"
BASE = "https://www.sbazar.cz"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
QUERIES = ["mountainbike", "celoodpruzené", "trail", "enduro", "horské kolo"]
CENA_OD = eur_to_czk(PRICE_EUR_MIN)
CENA_DO = eur_to_czk(PRICE_EUR_MAX)
MAX_PAGES = 8
FETCH_DETAILS = True
DETAIL_DELAY = 0.25


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_offers(html: str) -> list[dict]:
    text = unescape(html)
    seen: set[str] = set()
    items: list[dict] = []
    for m in re.finditer(r'"id":\[0,(\d+)\]', text):
        chunk = text[m.start() : m.start() + 5000]
        seo_m = re.search(r'"seoName":\[0,"([^"]+)"\]', chunk)
        name_m = re.search(r'"name":\[0,"([^"]+)"\]', chunk)
        price_m = re.search(r'"price":\[0,(\d+)\]', chunk)
        if not (seo_m and name_m and price_m):
            continue
        seo = seo_m.group(1)
        if not re.match(r"\d+-", seo):
            continue
        oid = seo.split("-", 1)[0]
        if oid in seen or not oid.isdigit() or int(oid) < 10_000_000:
            continue
        title = name_m.group(1).strip()
        if len(title) < 8 or title.lower() in {"kola", "auto-moto", "všechny kategorie"}:
            continue
        price = int(price_m.group(1))
        if price < CENA_OD or price > CENA_DO:
            continue
        seen.add(oid)
        city_m = re.search(r'"city":\[0,"([^"]*)"\]', chunk)
        region_m = re.search(r'"region":\[0,"([^"]*)"\]', chunk)
        loc = " ".join(x for x in [city_m.group(1) if city_m else "", region_m.group(1) if region_m else ""] if x)
        items.append({
            "id": oid,
            "source": "sbazar.cz",
            "title": title,
            "description": "",
            "price_czk": float(price),
            "price_eur": round(price / CZK_PER_EUR, 0),
            "location": loc,
            "url": f"{BASE}/inzerat/{seo}",
            "image_url": sbazar_image_from_chunk(chunk),
        })
    return items


def fetch_detail(item: dict) -> str:
    try:
        html = fetch(item["url"])
        text = unescape(html)
        # description in offer detail blob
        for m in re.finditer(r'"id":\[0,' + re.escape(item["id"]) + r'\]', text):
            chunk = text[m.start() : m.start() + 12000]
            img = sbazar_image_from_chunk(chunk)
            if img and not item.get("image_url"):
                item["image_url"] = img
            desc_m = re.search(r'"description":\[0,"((?:\\.|[^"\\])*)"\]', chunk)
            if desc_m:
                return desc_m.group(1).replace("\\n", " ").replace('\\"', '"')[:2000]
        m = re.search(r'<meta name="description" content="([^"]+)"', html)
        return m.group(1) if m else ""
    except Exception as e:
        print(f"    detail fail {item['id']}: {e}")
    return ""


def main() -> None:
    all_items: dict[str, dict] = {}
    for q in QUERIES:
        slug = urllib.parse.quote(q)
        for page in range(1, MAX_PAGES + 1):
            params = urllib.parse.urlencode({
                "cena_od": CENA_OD,
                "cena_do": CENA_DO,
                "strana": page,
            })
            url = f"{BASE}/hledej/{slug}?{params}"
            print(f"fetch {url}")
            try:
                html = fetch(url)
            except Exception as e:
                print(f"  fail: {e}")
                break
            batch = parse_offers(html)
            print(f"  page {page}: {len(batch)} offers")
            if not batch:
                break
            for it in batch:
                all_items[it["id"]] = it
            time.sleep(0.4)

    items = list(all_items.values())
    if FETCH_DETAILS:
        for i, it in enumerate(items):
            print(f"detail {i+1}/{len(items)} {it['id']}")
            it["description"] = fetch_detail(it)
            time.sleep(DETAIL_DELAY)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(items)} listings -> {OUT}")


if __name__ == "__main__":
    main()
