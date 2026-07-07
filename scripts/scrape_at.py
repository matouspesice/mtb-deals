"""Scrape willhaben MTB listings — whole Austria, 800–1900 EUR."""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "at_listings.json"

BASE_URL = (
    "https://www.willhaben.at/iad/kaufen-und-verkaufen/marktplatz/"
    "fahrraeder/mountainbikes-4559"
)
PARAMS = {
    "sfId": "c467bcb3-b965-4a60-9acb-cc8735d46d09",
    "rows": "90",
    "isNavigation": "true",
    "PRICE_FROM": "800",
    "PRICE_TO": "1900",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_next_data(html: str) -> dict | None:
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    return json.loads(m.group(1)) if m else None


def find_ad_objects(data: dict) -> list[dict]:
    found: list[dict] = []

    def walk(obj):
        if isinstance(obj, dict):
            keys = set(obj.keys())
            if {"id", "description", "attributes"}.issubset(keys) or (
                "id" in keys and "description" in keys and "advertImageList" in keys
            ):
                found.append(obj)
            elif "id" in keys and "description" in keys and any(
                k in keys for k in ("heading", "teaser", "advertiserInfo")
            ):
                found.append(obj)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(data)
    seen: set[str] = set()
    unique: list[dict] = []
    for item in found:
        aid = item.get("id")
        if aid and aid not in seen:
            seen.add(aid)
            unique.append(item)
    return unique


def normalize_item(raw: dict) -> dict:
    return {
        "id": raw.get("id"),
        "description": raw.get("description") or raw.get("teaser") or "",
        "attributes": raw.get("attributes") or {},
    }


def total_pages_from_data(data: dict) -> int | None:
    blob = json.dumps(data)
    m = re.search(r'"totalResults?":\s*(\d+)', blob)
    if not m:
        m = re.search(r'"rowsFound":\s*(\d+)', blob)
    if not m:
        return None
    total = int(m.group(1))
    return max(1, (total + 89) // 90)


def fetch_page(page: int) -> tuple[list[dict], int | None]:
    qs = urllib.parse.urlencode({**PARAMS, "page": str(page)})
    url = f"{BASE_URL}?{qs}"
    print(f"Page {page}...", end=" ", flush=True)
    html = fetch(url)
    nd = extract_next_data(html)
    if not nd:
        print("no data")
        return [], None
    pages = total_pages_from_data(nd) if page == 1 else None
    ads = find_ad_objects(nd)
    print(f"{len(ads)} ads")
    return [normalize_item(a) for a in ads], pages


def main() -> None:
    all_items: list[dict] = []
    max_pages = 55

    for page in range(1, max_pages + 1):
        try:
            items, total_pages = fetch_page(page)
            if total_pages:
                max_pages = total_pages
                print(f"  -> {total_pages} pages total")
            if not items:
                break
            all_items.extend(items)
            time.sleep(0.35)
        except Exception as e:
            print(f"ERROR: {e}")
            break

    seen: set[str] = set()
    unique = [x for x in all_items if x["id"] not in seen and not seen.add(x["id"])]  # type: ignore

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False)
    print(f"\nSaved {len(unique)} listings -> {OUT}")


if __name__ == "__main__":
    main()
