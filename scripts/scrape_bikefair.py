"""Scrape BikeFair mountain bikes from SSR HTML cards."""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from filters import PRICE_EUR_MAX, PRICE_EUR_MIN

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "bikefair_listings.json"
BASE = "https://bikefair.org"
LIST_URL = f"{BASE}/c/mountain-bikes"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
SKIP_SLUG = ("sample", "omafiets", "gazelle", "batavus", "sparta", "fatbike", "elektrisch", "e-bike")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_cards(html: str) -> list[dict]:
    items: list[dict] = []
    for m in re.finditer(r'<a href="(/bikes/[a-f0-9-]+/[^"?]+)', html):
        path = m.group(1).replace("&amp;", "&")
        slug = path.split("/")[-1].lower()
        if any(s in slug for s in SKIP_SLUG):
            continue
        start = m.start()
        chunk = html[start : start + 10000]
        uuid = re.search(r"/bikes/([a-f0-9-]+)/", path)
        title_m = re.search(r'class="[^"]*font-semibold[^"]*"[^>]*>\s*([^<]+?)\s*<', chunk)
        if not title_m:
            title_m = re.search(r'class="[^"]*font-headline[^"]*"[^>]*>([^<]+)<', chunk)
        price_m = re.search(r"€\s*([\d\s.,]+)", chunk)
        size_m = re.search(r"(\d{2})\s*cm", chunk, re.I)
        loc_m = re.search(r'fa-map-marker[^>]*></i>\s*([^<]+)<', chunk)
        desc_m = re.search(r"<p[^>]*>\s*([^<]{10,220})\s*</p>", chunk)

        if not price_m:
            continue
        price_raw = price_m.group(1).replace(" ", "").replace(",", "")
        try:
            price_eur = float(price_raw)
        except ValueError:
            continue
        if not (PRICE_EUR_MIN <= price_eur <= PRICE_EUR_MAX):
            continue

        title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else slug.replace("-", " ")
        items.append({
            "id": uuid.group(1) if uuid else path,
            "source": "bikefair.org",
            "title": title,
            "description": ((desc_m.group(1) if desc_m else "") + (f" {size_m.group(0)}" if size_m else "")).strip(),
            "price_eur": price_eur,
            "location": loc_m.group(1).strip() if loc_m else "",
            "url": BASE + path.split("?")[0],
        })
    # dedupe within page
    seen: set[str] = set()
    unique: list[dict] = []
    for it in items:
        if it["id"] not in seen:
            seen.add(it["id"])
            unique.append(it)
    return unique


def fetch_detail(item: dict) -> None:
    try:
        html = fetch(item["url"])
        m = re.search(r'class="[^"]*prose[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL | re.I)
        if m:
            body = re.sub(r"<[^>]+>", " ", m.group(1))
            body = re.sub(r"\s+", " ", body).strip()[:1200]
            item["description"] = f"{item['title']} {body}"
        specs = re.findall(
            r"(?:Frame size|Rahmengröße|Travel|Federweg|Year|Baujahr)[:\s]*[^<\n]{2,40}",
            html,
            re.I,
        )
        if specs:
            item["description"] += " " + " ".join(specs[:6])
    except Exception:
        pass


def main() -> None:
    all_items: dict[str, dict] = {}
    q = urllib.parse.urlencode({
        "price_max": str(PRICE_EUR_MAX),
        "frame_height_min": "170",
        "frame_height_max": "190",
    })
    url = f"{LIST_URL}?{q}"
    print(f"Fetching {url}")
    html = fetch(url)
    batch = parse_cards(html)
    for b in batch:
        all_items[b["id"]] = b
    print(f"SSR cards in price range: {len(batch)} (BikeFair loads more client-side)")

    items = list(all_items.values())
    print(f"Fetching details for {len(items)}...")
    for i, it in enumerate(items, 1):
        if PRICE_EUR_MIN <= (it.get("price_eur") or 0) <= PRICE_EUR_MAX or it.get("price_eur") is None:
            fetch_detail(it)
        if i % 20 == 0:
            print(f"  {i}/{len(items)}")
        time.sleep(0.15)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(items)} -> {OUT}")


if __name__ == "__main__":
    main()
