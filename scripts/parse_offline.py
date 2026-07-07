"""Parse offline willhaben MHTML listing pages into listings.json."""
from __future__ import annotations

import json
import re
from email import message_from_bytes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFLINE_DIR = ROOT / "offline-pages"
OUT = ROOT / "data" / "listings.json"


def load_html_from_mhtml(path: Path) -> str:
    raw = path.read_bytes()
    msg = message_from_bytes(raw)
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True)
            if payload:
                return payload.decode("utf-8", errors="replace")
    return raw.decode("utf-8", errors="replace")


def parse_price(text: str) -> float | None:
    text = text.replace("\u00a0", " ").replace("€", "").strip()
    text = text.replace(".", "").replace(",", ".")
    m = re.search(r"[\d.]+", text)
    return float(m.group()) if m else None


def parse_listings(html: str) -> list[dict]:
    listings = []
    # Each result card: div with numeric id + search-result-entry-header link
    card_re = re.compile(
        r'id="(\d+)"[^>]*class="[^"]*jhFncg[^"]*"[^>]*>'
        r'.*?'
        r'href="(https://www\.willhaben\.at/iad/kaufen-und-verkaufen/d/[^"]+)"'
        r'.*?'
        r'data-testid="search-result-entry-header-\1"'
        r'.*?'
        r'<h3[^>]*>(.*?)</h3>'
        r'.*?'
        r'data-testid="search-result-entry-price-\1"[^>]*>(.*?)</span>'
        r'.*?'
        r'class="[^"]*goTIWT[^"]*"[^>]*>(.*?)</span>'
        r'.*?'
        r'aria-label="Wird verkauft in ([^"]+)"',
        re.DOTALL,
    )
    for m in card_re.finditer(html):
        ad_id, url, title, price_raw, teaser, location = m.groups()
        title = re.sub(r"<[^>]+>", "", title).strip()
        teaser = re.sub(r"<[^>]+>", "", teaser).strip()
        listings.append({
            "id": ad_id,
            "title": title,
            "description": teaser,
            "price": parse_price(price_raw),
            "location": location.strip(),
            "url": url.replace("&amp;", "&"),
        })
    return listings


def main() -> None:
    files = sorted(OFFLINE_DIR.glob("*.mhtml"))
    if not files:
        raise SystemExit(f"No .mhtml files in {OFFLINE_DIR}")

    all_items: list[dict] = []
    for path in files:
        html = load_html_from_mhtml(path)
        items = parse_listings(html)
        print(f"{path.name}: {len(items)} listings")
        all_items.extend(items)

    seen: set[str] = set()
    unique: list[dict] = []
    for item in all_items:
        if item["id"] not in seen:
            seen.add(item["id"])
            unique.append(item)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    print(f"\nTotal unique: {len(unique)} -> {OUT}")


if __name__ == "__main__":
    main()
