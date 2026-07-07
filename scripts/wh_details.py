import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent

IDS = [
    "1185184506",  # Epic Expert L 800
    "1699823866",  # Rocky Mountain Altitude M 1050
    "1298720294",  # Cube Stereo 160 1150
    "1310526614",  # Santa Cruz Nomad M 1450
    "1032155251",  # Cube AMS L 1500
    "2130523117",  # Trek X-Caliber 9 900
    "808064613",   # Trek Slash 9.9
    "1810675315",  # Ghost Riot
    "860681608",   # Custom hardtail
    "1663511118",  # Canyon Spectral XTR M 880
]

with open(DATA_DIR / "wh_results.json", encoding="utf-8") as f:
    items = {x["id"]: x for x in json.load(f)}

for i in IDS:
    item = items.get(i)
    if not item:
        print(f"MISSING {i}\n")
        continue
    attrs = {}
    for a in item["attrs"].get("attribute", []):
        attrs[a["name"]] = a["values"][0] if len(a["values"]) == 1 else a["values"]
    print("=" * 70)
    print(attrs.get("HEADING", ""))
    print(f"€{attrs.get('PRICE/AMOUNT')} | {attrs.get('POSTCODE')} {attrs.get('LOCATION')}")
    seo = attrs.get("SEO_URL", "")
    if seo:
        print(f"https://www.willhaben.at/iad/{seo}")
    body = attrs.get("BODY_DYN", attrs.get("BODY", ""))
    print(body[:1200])
    print()
