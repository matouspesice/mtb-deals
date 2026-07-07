"""Re-analyze wh_results.json with proper attribute parsing."""
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent

with open(DATA_DIR / "wh_results.json", encoding="utf-8") as f:
    items = json.load(f)


def attr_map(attrs):
    out = {}
    raw = attrs.get("attribute") if isinstance(attrs, dict) else None
    if not raw:
        return out
    for a in raw:
        name = a.get("name", "")
        vals = a.get("values") or []
        out[name] = vals[0] if len(vals) == 1 else vals
    return out


def full_text(item):
    a = attr_map(item["attrs"])
    parts = [
        item.get("title") or "",
        item.get("description") or "",
        str(a.get("HEADING", "")),
        str(a.get("BODY_DYN", "")),
        str(a.get("BODY", "")),
    ]
    return " ".join(parts)


def price_eur(item):
    a = attr_map(item["attrs"])
    p = a.get("PRICE/AMOUNT") or a.get("PRICE")
    try:
        return float(str(p).replace(",", "."))
    except (TypeError, ValueError):
        return None


def willhaben_url(item):
    ad_id = item.get("id")
    heading = attr_map(item["attrs"]).get("HEADING", item.get("description", "bike"))
    slug = re.sub(r"[^a-zA-Z0-9äöüÄÖÜß]+", "-", str(heading).lower()).strip("-")[:80]
    return f"https://www.willhaben.at/iad/kaufen-und-verkaufen/d/gebraucht/{slug}-{ad_id}/"


def frame_fit_183(text):
    t = text.lower()
    # explicit bad
    if re.search(r"größe\s*xl|größe\s*21|größe\s*22|rahmen.*\bxl\b|size\s*xl|\b22\s*[\"']", t):
        if not re.search(r"größe\s*l\b|size\s*l\b|gr\.?\s*l\b|\b19[,.]?5", t):
            return "unlikely", "XL or too large"
    if re.search(r"größe\s*s\b|größe\s*xs|rahmen.*\bs\b|size\s*s\b|\b15\s*[\"']|\b16\s*[\"']", t):
        if not re.search(r"größe\s*l\b|größe\s*m\b|\b17\s*[\"']|\b18\s*[\"']|\b19\s*[\"']", t):
            return "unlikely", "S/XS or too small"

    if re.search(r"größe\s*l\b|size\s*l\b|gr\.?\s*l\b|\b19[,.]?5\s*[\"']|\b19\s*[\"']|\b58\s*cm", t):
        return "likely_fit", "L / 19\""
    if re.search(r"größe\s*m\b|size\s*m\b|gr\.?\s*m\b|\b17\s*[\"']|\b18\s*[\"']|\b56\s*cm|rh\s*5[4-7]", t):
        return "likely_fit", "M / 17-18\""
    if re.search(r"\bs3\b", t):  # Specialized S3 ~ medium-large
        return "likely_fit", "Specialized S3"
    if re.search(r"183\s*cm|1[.,]83\s*m", t):
        return "likely_fit", "mentions 183cm"

    return "unknown", "size not stated"


def deal_score(text, price, fit):
    t = text.lower()
    score = 0
    notes = []

    premium = [
        ("fox factory", 3), ("fox 36", 2), ("fox 34", 1), ("xt ", 2), ("x01", 3), ("xx1", 3),
        ("gx eagle", 1), ("carbon fully", 3), ("carbonrahmen", 1), ("dropper", 1),
        ("originalrechnung", 2), ("rechnung vorhanden", 2), ("neuwertig", 2),
        ("kaum gefahren", 2), ("wenig gefahren", 2), ("300 km", 2), ("500 km", 1),
        ("top zustand", 1), ("sehr guter zustand", 1), ("garantie", 1),
    ]
    for kw, pts in premium:
        if kw in t:
            score += pts
            notes.append(kw)

    bad = ["defekt", "rahmenriss", "unfall", "reparaturbedürftig", "händler", "shop", "aktion"]
    for kw in bad:
        if kw in t:
            score -= 3
            notes.append(f"!{kw}")

    if "vb" in t or "verhandlungsbasis" in t:
        score += 1
        notes.append("VB")

    # naive market value bands (used market AT, rough)
    if price:
        if price <= 1100 and any(k in t for k in ("xt", "fox", "carbon", "fully", "santa cruz", "specialized", "trek fuel", "cube stereo")):
            score += 5
            notes.append(f"LOW PRICE €{price:.0f} for spec")
        elif price <= 1500 and any(k in t for k in ("xt", "x01", "fox 36", "carbon fully", "slash", "stumpjumper", "capra")):
            score += 4
            notes.append(f"underpriced €{price:.0f}?")
        elif price <= 2000 and any(k in t for k in ("xx1", "fox factory", "xtr", "9.9", "factory")):
            score += 3
            notes.append(f"high-end €{price:.0f}")

    if fit == "likely_fit":
        score += 2
    elif fit == "unlikely":
        score -= 8

    return score, notes


enriched = []
for item in items:
    text = full_text(item)
    price = price_eur(item)
    fit, fit_reason = frame_fit_183(text)
    score, notes = deal_score(text, price, fit)
    a = attr_map(item["attrs"])
    enriched.append({
        "id": item["id"],
        "title": a.get("HEADING", item.get("description", ""))[:100],
        "price": price,
        "location": f"{a.get('POSTCODE','')} {a.get('LOCATION','')}, {a.get('DISTRICT','')}",
        "fit": fit,
        "fit_reason": fit_reason,
        "score": score,
        "notes": notes,
        "url": willhaben_url(item),
        "snippet": text[:350].replace("\n", " "),
    })

# Best: likely fit + high score
best_fit = [e for e in enriched if e["fit"] == "likely_fit" and e["score"] >= 5]
best_fit.sort(key=lambda x: (-x["score"], x["price"] or 9999))

# Hidden gems: unknown size but amazing price/spec (worth asking)
gems = [e for e in enriched if e["fit"] == "unknown" and e["score"] >= 8]
gems.sort(key=lambda x: (-x["score"], x["price"] or 9999))

# Dump for assistant
print("=== BEST FOR 183cm (M/L confirmed) ===\n")
for e in best_fit[:20]:
    print(f"€{e['price']:.0f} | score {e['score']} | {e['fit_reason']}")
    print(f"  {e['title']}")
    print(f"  {e['location']}")
    print(f"  {e['url']}")
    print(f"  Notes: {', '.join(e['notes'][:8])}")
    print()

print("\n=== HIDDEN GEMS (check size — seller may not know value) ===\n")
for e in gems[:15]:
    print(f"€{e['price']:.0f} | score {e['score']} | SIZE UNKNOWN")
    print(f"  {e['title']}")
    print(f"  {e['location']}")
    print(f"  {e['url']}")
    print(f"  Notes: {', '.join(e['notes'][:8])}")
    print()

out = DATA_DIR / "wh_top_deals.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump({"best_fit": best_fit[:30], "gems": gems[:20]}, f, ensure_ascii=False, indent=2)
print(f"Saved {out}")
