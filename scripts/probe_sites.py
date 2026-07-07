"""Quick probe of marketplace site structures."""
import json
import re
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent.parent / "data" / "probe"
OUT.mkdir(parents=True, exist_ok=True)

SITES = {
    "bazos": "https://www.bazos.cz/search.php?hledat=mountainbike&rubriky=sport&cenaod=15000&cenado=70000",
    "bazos2": "https://www.bazos.cz/search.php?hledat=&rubriky=sport&hledat=kolo&cenaod=15000&cenado=70000",
    "sbazar": "https://www.sbazar.cz/hledej/mountainbike?cena_od=15000&cena_do=70000",
    "bikefair": "https://bikefair.org/bikes?category=mountain-bikes&price_max=3000",
    "kleinanzeigen": "https://www.kleinanzeigen.de/s-mountainbike/anzeige:angebote/preis:800:2500",
}

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


for name, url in SITES.items():
    print(f"\n=== {name} ===")
    try:
        html = fetch(url)
        path = OUT / f"{name}.html"
        path.write_text(html[:500000], encoding="utf-8")
        print(f"  saved {len(html)} -> {path.name}")

        if name.startswith("bazos"):
            blocks = re.findall(
                r'<div class="inzeraty[^"]*">(.*?)</table>',
                html,
                re.DOTALL,
            )
            print(f"  inzeraty blocks: {len(blocks)}")
            for b in blocks[:2]:
                t = re.search(r'inzeratynadpis.*?<a[^>]*>([^<]+)', b, re.DOTALL)
                p = re.search(r'inzeratycena[^>]*>.*?<b>([^<]+)', b, re.DOTALL)
                if t:
                    print(f"    {p.group(1) if p else '?'} | {t.group(1)[:50]}")

        if name == "sbazar":
            for pat in [r'data-testid="[^"]*card', r'/inzerat/', r'class="[^"]*Item[^"]*"']:
                print(f"  {pat}: {len(re.findall(pat, html))}")

        if name == "kleinanzeigen":
            ads = re.findall(r'data-adid="(\d+)"', html)
            print(f"  adids: {len(ads)}")
            titles = re.findall(r'class="ellipsis"[^>]*>([^<]+)', html)
            print(f"  titles sample: {titles[:3]}")

        if name == "bikefair":
            m = re.search(r'window\.__NUXT__\s*=\s*(.+?)</script>', html, re.DOTALL)
            print(f"  NUXT block: {bool(m)} len={len(m.group(1)) if m else 0}")
    except Exception as e:
        print(f"  FAIL: {e}")
