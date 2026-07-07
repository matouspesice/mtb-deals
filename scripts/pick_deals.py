import json
from pathlib import Path

d = json.load(open(Path(__file__).parent.parent / "data" / "at_trail_deals.json", encoding="utf-8"))
items = [
    x for x in d["top"]
    if (x.get("year") or 0) >= 2020 and (x.get("price") or 9999) <= 1800
]
items.sort(key=lambda x: (-x["score"], x["price"] or 9999))
for e in items[:25]:
    print(f"{e['price']:.0f} MY{e.get('year')} {e['travel']} {e['fit']} | {e['title'][:75]}")
    print(f"  {e['location']}")
    print(f"  {e['url']}\n")
