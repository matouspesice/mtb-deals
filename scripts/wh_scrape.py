"""Scrape willhaben MTB listings and find deals for 183cm / M-L frame."""
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent

BASE_URL = (
    "https://www.willhaben.at/iad/kaufen-und-verkaufen/marktplatz/"
    "fahrraeder/mountainbikes-4559"
)
PARAMS = {
    "areaId": "7",
    "sfId": "c467bcb3-b965-4a60-9acb-cc8735d46d09",
    "rows": "30",
    "isNavigation": "true",
    "PRICE_FROM": "800",
    "PRICE_TO": "2500",
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
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_next_data(html: str) -> dict | None:
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not m:
        return None
    return json.loads(m.group(1))


def extract_listings_from_html(html: str) -> list[dict]:
    """Fallback: regex extract listing cards from rendered HTML."""
    listings = []
    # Pattern for listing links
    for m in re.finditer(
        r'href="(/iad/kaufen-und-verkaufen/d/[^"]+)"[^>]*>.*?'
        r'(?:€\s*([\d.,]+))?\s*([^<]{5,120})',
        html,
        re.DOTALL,
    ):
        listings.append({"url": m.group(1), "price": m.group(2), "title": m.group(3)})
    return listings


def parse_listings_from_next(data: dict) -> list[dict]:
    listings = []
    text = json.dumps(data)

    def walk(obj, path=""):
        if isinstance(obj, dict):
            if "id" in obj and "description" in obj and "description" in str(obj.get("description", "")):
                listings.append(obj)
            if "advertSummaryList" in obj:
                for item in obj["advertSummaryList"]:
                    listings.append(item)
            if "advertiserInfo" in obj and "id" in obj:
                listings.append(obj)
            for k, v in obj.items():
                walk(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")

    walk(data)
    return listings


def find_ad_objects(data: dict) -> list[dict]:
    """Find advert-like objects anywhere in NEXT_DATA."""
    found = []

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
    # dedupe by id
    seen = set()
    unique = []
    for item in found:
        aid = item.get("id")
        if aid and aid not in seen:
            seen.add(aid)
            unique.append(item)
    return unique


SIZE_RE = re.compile(
    r"(?i)"
    r"(?:rahmen(?:größe|groesse|size)?|größe|groesse|size|rahmen)"
    r"[\s:]*"
    r"(\d{2})\s*(?:\"|''|zoll|inch)?"
    r"|"
    r"\b(size\s*)?([ML])\b"
    r"|"
    r"\b(\d{2})\s*(?:\"|''|zoll)\b"
    r"|"
    r"\b(Medium|Large|Gr\.?\s*M|Gr\.?\s*L)\b"
)


def frame_fit(desc: str, title: str = "") -> dict:
    text = f"{title} {desc}"
    sizes_inch = []
    letter = None
    for m in SIZE_RE.finditer(text):
        g1, g2, g3, g4 = m.group(1), m.group(2), m.group(3), m.group(4)
        if g1 and g1.isdigit():
            sizes_inch.append(int(g1))
        if g2:
            letter = g2.upper()
        if g3 and g3.isdigit():
            sizes_inch.append(int(g3))
        if g4:
            s = g4.upper()
            if re.search(r"\bM\b|GR\.?\s*M|MEDIUM", s):
                letter = "M"
            elif re.search(r"\bL\b|GR\.?\s*L|LARGE", s):
                letter = "L"

  # 183cm typical MTB: M-L, roughly 17-19" or 54-58cm
    fit = "unknown"
    if letter in ("M", "L"):
        fit = "likely_fit"
    elif any(17 <= s <= 19 for s in sizes_inch):
        fit = "likely_fit"
    elif any(s in (16, 20) for s in sizes_inch):
        fit = "borderline"
    elif letter in ("S", "XS", "XL", "XXL") or any(s <= 15 or s >= 21 for s in sizes_inch):
        fit = "unlikely"

    return {"fit": fit, "sizes_inch": sizes_inch, "letter": letter}


DEAL_KEYWORDS_HIGH = [
    "xt ", "xtr", "sram gx", "sram x01", "sram xx1", "fox ", "rockshox",
    "carbon", "full suspension", "fully", "dropper", "rechnung", "neuwertig",
    "kaum gefahren", "wenig gefahren", "originalrechnung", "garantie",
    "shimano slx", "deore xt", "fox 34", "fox 36", "marzocchi",
    "specialized", "trek ", "canyon", "scott spark", "scott genius",
    "cube stereo", "propain", "yt ", "commencal", "santa cruz",
]

DEAL_KEYWORDS_LOW = [
    "defekt", "reparatur", "rahmenriss", "gebrochen", "unfall",
    "verkaufe weil", "nicht mehr fahre", "steht nur", "lange nicht",
]


def score_deal(item: dict) -> tuple[int, list[str]]:
    title = (item.get("heading") or item.get("title") or "").lower()
    desc = (item.get("description") or item.get("teaser") or "").lower()
    text = f"{title} {desc}"
    price = item.get("price") or item.get("priceForDisplay") or ""
    if isinstance(price, (int, float)):
        price_num = float(price)
    else:
        pm = re.search(r"[\d.]+", str(price).replace(".", "").replace(",", "."))
        price_num = float(pm.group()) if pm else 0

    score = 0
    reasons = []

    for kw in DEAL_KEYWORDS_HIGH:
        if kw in text:
            score += 2
            reasons.append(f"+{kw.strip()}")

    for kw in DEAL_KEYWORDS_LOW:
        if kw in text:
            score -= 3
            reasons.append(f"-{kw}")

    if "vb" in text or "verhandlungsbasis" in text:
        score += 1
        reasons.append("VB (negotiable)")

    if any(x in text for x in ("kaum", "wenig gefahren", "300 km", "500 km", "neu gekauft")):
        score += 2
        reasons.append("low mileage hint")

    if "rechnung" in text or "originalrechnung" in text:
        score += 2
        reasons.append("receipt")

    if "händler" in text or "shop" in text or "aktion" in title:
        score -= 4
        reasons.append("dealer/shop listing")

    # rough value heuristics
    if price_num and price_num <= 1200:
        if any(k in text for k in ("xt", "fox", "carbon", "fully", "santa cruz", "specialized")):
            score += 4
            reasons.append("premium spec at low price")

    if price_num and 1200 < price_num <= 1800:
        if any(k in text for k in ("xt", "x01", "fox 36", "carbon fully")):
            score += 3
            reasons.append("high-end under 1800")

    return score, reasons


def normalize_item(raw: dict) -> dict:
    attrs = raw.get("attributes", {}) or {}
    if isinstance(attrs, list):
        attr_dict = {}
        for a in attrs:
            if isinstance(a, dict):
                name = a.get("name") or a.get("attributeName") or ""
                val = a.get("values") or a.get("value") or ""
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                attr_dict[name] = val
        attrs = attr_dict

    desc = raw.get("description") or raw.get("teaser") or ""
    title = raw.get("heading") or raw.get("title") or ""
    price = raw.get("price") or raw.get("priceForDisplay") or attrs.get("PRICE") or ""
    ad_id = raw.get("id") or raw.get("adId")
    url = raw.get("selfLink") or raw.get("seoLink") or ""
    if url and not url.startswith("http"):
        url = "https://www.willhaben.at" + url
    if ad_id and not url:
        slug = raw.get("slug") or ""
        url = f"https://www.willhaben.at/iad/kaufen-und-verkaufen/d/gebraucht/{ad_id}"

    return {
        "id": ad_id,
        "title": title,
        "description": desc,
        "price": price,
        "url": url,
        "attrs": attrs,
        "raw_keys": list(raw.keys())[:15],
    }


def try_bff_api(page: int) -> dict | None:
    qs = urllib.parse.urlencode({**PARAMS, "page": str(page)})
    urls = [
        f"https://www.willhaben.at/webapi/bff/search/atz/seo/kaufen-und-verkaufen/marktplatz/fahrraeder/mountainbikes-4559?{qs}",
        f"https://www.willhaben.at/webapi/bff/atz/seo/kaufen-und-verkaufen/marktplatz/fahrraeder/mountainbikes-4559?{qs}",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(
                url,
                headers={**HEADERS, "Accept": "application/json", "x-wh-client": "web"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            print(f"  API fail {url[:80]}: {e}")
    return None


def fetch_page_listings(page: int) -> list[dict]:
    qs = urllib.parse.urlencode({**PARAMS, "page": str(page)})
    url = f"{BASE_URL}?{qs}"
    print(f"Fetching page {page}...")
    html = fetch(url)
    nd = extract_next_data(html)
    if not nd:
        print(f"  No __NEXT_DATA__ on page {page}")
        return []
    ads = find_ad_objects(nd)
    print(f"  {len(ads)} ads")
    return [normalize_item(a) for a in ads]


def main():
    all_items = []

    # Paginate via HTML __NEXT_DATA__ (640 ads / 30 per page ≈ 22 pages)
    for page in range(1, 23):
        try:
            items = fetch_page_listings(page)
            if not items:
                break
            all_items.extend(items)
            time.sleep(0.4)
        except Exception as e:
            print(f"  Error page {page}: {e}")
            break

    # Dedupe
    seen = set()
    unique = []
    for item in all_items:
        key = item.get("id") or item.get("url") or item.get("title")
        if key and key not in seen:
            seen.add(key)
            unique.append(item)

    print(f"\nTotal unique listings: {len(unique)}")

    if not unique:
        # dump html snippets for debugging
        for pat in ["Cube", "Santa Cruz", "advertId", "__NEXT_DATA__", "advertSummary"]:
            idx = html.find(pat)
            print(f"  html search '{pat}': {idx}")
        with open(DATA_DIR / "wh_debug_snippet.txt", "w", encoding="utf-8") as f:
            for pat in ["Cube", "Santa Cruz", "advertSummary", "description"]:
                idx = html.find(pat)
                if idx >= 0:
                    f.write(f"\n--- {pat} at {idx} ---\n")
                    f.write(html[max(0, idx - 200) : idx + 800])
        print("Wrote wh_debug_snippet.txt")
        return

    scored = []
    for item in unique:
        fit = frame_fit(item["description"], item["title"])
        score, reasons = score_deal(item)
        if fit["fit"] == "likely_fit":
            score += 3
        elif fit["fit"] == "borderline":
            score += 1
        elif fit["fit"] == "unlikely":
            score -= 5
        scored.append({**item, "fit": fit, "score": score, "reasons": reasons})

    scored.sort(key=lambda x: x["score"], reverse=True)

    print("\n=== TOP DEALS (M/L fit for 183cm) ===\n")
    top = [s for s in scored if s["fit"]["fit"] in ("likely_fit", "borderline", "unknown") and s["score"] >= 4]
    for i, s in enumerate(top[:25], 1):
        print(f"{i}. [{s['score']}] {s['title'][:80]}")
        print(f"   Price: {s['price']} | Fit: {s['fit']}")
        print(f"   Reasons: {', '.join(s['reasons'][:6])}")
        print(f"   {s['url']}")
        print(f"   Desc: {s['description'][:200]}...")
        print()

    out = DATA_DIR / "wh_results.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(scored, f, ensure_ascii=False, indent=2)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
