"""Scrape sport.bazos.cz — MTB / fully listings."""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from filters import CZK_PER_EUR, PRICE_EUR_MAX, PRICE_EUR_MIN, eur_to_czk

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "bazos_listings.json"

BASE = "https://sport.bazos.cz"
QUERIES = ["kolo", "celoodpružené", "trail", "enduro"]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
CENA_OD = eur_to_czk(PRICE_EUR_MIN)
CENA_DO = eur_to_czk(PRICE_EUR_MAX)
MAX_PAGES_PER_QUERY = 25  # 20 ads/page
FETCH_DETAILS = True
DETAIL_DELAY = 0.2


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_price_czk(raw: str) -> float | None:
    raw = raw.replace("\u00a0", " ").replace("Kč", "").strip()
    raw = re.sub(r"[^\d]", "", raw)
    return float(raw) if raw else None


def parse_list_page(html: str) -> list[dict]:
    items: list[dict] = []
    blocks = re.split(r'<div class="inzeraty inzeratyflex">', html)
    for block in blocks[1:]:
        m_url = re.search(r'<h2 class=nadpis><a href="([^"]+)">([^<]+)</a>', block)
        if not m_url:
            continue
        path, title = m_url.groups()
        m_price = re.search(r'inzeratycena.*?<b>.*?([\d\s]+)\s*Kč', block, re.DOTALL)
        m_loc = re.search(r'inzeratylok">([^<]+)<br>([^<]*)<', block)
        m_popis = re.search(r'<div class=popis>(.*?)</div>', block, re.DOTALL)
        popis = re.sub(r"<[^>]+>", "", m_popis.group(1)) if m_popis else ""
        popis = re.sub(r"\s+", " ", popis).strip()
        price = parse_price_czk(m_price.group(1)) if m_price else None
        loc = f"{m_loc.group(1).strip()} {m_loc.group(2).strip()}".strip() if m_loc else ""
        full_url = path if path.startswith("http") else BASE + path
        ad_id = re.search(r"/inzerat/(\d+)/", path)
        aid = ad_id.group(1) if ad_id else ""
        img_m = re.search(r'<img[^>]+src="([^"]+)"[^>]*class="obrazek"', block)
        image_url = img_m.group(1) if img_m else None
        if not image_url and aid.isdigit():
            image_url = f"https://www.bazos.cz/img/1t/{aid[-3:]}/{aid}.jpg"
        items.append({
            "id": aid or path,
            "source": "bazos.cz",
            "title": title.strip(),
            "description": popis,
            "price_czk": price,
            "price_eur": round(price / CZK_PER_EUR, 0) if price else None,
            "location": loc,
            "url": full_url,
            "image_url": image_url,
        })
    return items


def fetch_detail(item: dict) -> str:
    try:
        html = fetch(item["url"])
        m = re.search(r'<div class=["\']popisdetail["\']>(.*?)</div>', html, re.DOTALL)
        if not m:
            m = re.search(r'<div class=["\']popis["\']>(.*?)</div>', html, re.DOTALL)
        if m:
            text = re.sub(r"<[^>]+>", " ", m.group(1))
            return re.sub(r"\s+", " ", text).strip()
    except Exception as e:
        print(f"    detail fail {item['id']}: {e}")
    return ""


def search_url(query: str, offset: int) -> str:
    params = {
        "hledat": query,
        "hlokalita": "",
        "humkreis": "",
        "cenaod": str(CENA_OD),
        "cenado": str(CENA_DO),
        "order": "",
    }
    qs = urllib.parse.urlencode(params)
    prefix = f"/{offset}/" if offset else "/"
    return f"{BASE}{prefix}?{qs}"


def main() -> None:
    all_items: dict[str, dict] = {}

    for query in QUERIES:
        print(f"\nQuery: {query!r}")
        for page in range(MAX_PAGES_PER_QUERY):
            offset = page * 20
            url = search_url(query, offset)
            try:
                html = fetch(url)
                batch = parse_list_page(html)
                if not batch:
                    print(f"  page {page+1}: empty, stop")
                    break
                new = 0
                for it in batch:
                    if it["id"] not in all_items:
                        all_items[it["id"]] = it
                        new += 1
                print(f"  page {page+1}: +{new} new (total {len(all_items)})")
                if new == 0:
                    break
                time.sleep(0.3)
            except Exception as e:
                print(f"  page {page+1} error: {e}")
                break

    def wants_detail(it: dict) -> bool:
        t = f"{it['title']} {it['description']}".lower()
        if any(x in t for x in ("hardtail", "e-bike", "elektro", "gravel", "dětsk", "detsk")):
            return False
        return any(x in t for x in (
            "celoodpru", "fully", "full ", " fs", "trail", "enduro", "tlumič", "tlumic",
            "fuel", "spectral", "stumpjumper", "capra", "process", "fluid", "genius",
        ))

    items = list(all_items.values())
    detail_targets = [it for it in items if wants_detail(it)] if FETCH_DETAILS else []
    if FETCH_DETAILS and detail_targets:
        print(f"\nFetching details for {len(detail_targets)}/{len(items)} listings...")
        for i, it in enumerate(detail_targets, 1):
            extra = fetch_detail(it)
            if extra:
                it["description"] = f"{it['description']} {extra}".strip()
            if i % 25 == 0:
                print(f"  {i}/{len(detail_targets)}")
            time.sleep(DETAIL_DELAY)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(items)} -> {OUT}")


if __name__ == "__main__":
    main()
