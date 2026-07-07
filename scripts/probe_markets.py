"""Probe niche marketplace HTML structures."""
import re
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent.parent / "data" / "probe"
OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}

SITES = {
    "cyklobazar": "https://www.cyklobazar.cz/celoodpruzena-kola?cena_od=20000&cena_do=47500",
    "mtbiker": "https://www.mtbiker.cz/bazar/kola/horska/celoodpruzena?cena_od=20000&cena_do=47500",
    "radbazar": "https://www.radbazar.at/categories/mountainbikes?price_min=800&price_max=1900",
    "biklo": "https://www.biklo.cz/bazar/horska-kola/celoodpruzena?cena_od=20000&cena_do=47500",
    "kleinanzeigen_at": "https://www.kleinanzeigen.at/Marktplatz/Sportartikel-Outdoorzubehoer/Fahrraeder-Radsport/Mountainbikes-Trekkingraeder?preis_von=800&preis_bis=1900",
    "pinkbike": "https://www.pinkbike.com/buysell/list/?region=3&category=75&price=800-1900",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", errors="replace")


for name, url in SITES.items():
    print(f"\n=== {name} ===")
    try:
        html = fetch(url)
        path = OUT / f"market_{name}.html"
        path.write_text(html[:800000], encoding="utf-8")
        print(f"  len={len(html)} -> {path.name}")
        for pat in [r'href="[^"]*inzerat[^"]*"', r'href="/listing/', r'href="/bazar/', r'data-adid', r'__NEXT_DATA__', r'application/ld\+json']:
            c = len(re.findall(pat, html, re.I))
            if c:
                print(f"  {pat}: {c}")
        links = re.findall(r'href="(/[^"]{10,120})"', html)[:5]
        print(f"  sample links: {links}")
    except Exception as e:
        print(f"  FAIL: {e}")
