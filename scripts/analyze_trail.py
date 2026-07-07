"""Filter AT listings: full-sus trail/AM ~150mm, 2019+, M/L for 183cm, best deals."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INP = ROOT / "data" / "at_listings.json"
OUT = ROOT / "data" / "at_trail_deals.json"

from filters import PRICE_EUR_MAX, PRICE_EUR_MIN, model_year as filter_model_year

MIN_YEAR = 2019
TRAVEL_MIN = 130
TRAVEL_MAX = 170


def attr_map(attrs: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    raw = attrs.get("attribute") if isinstance(attrs, dict) else None
    if not raw:
        return out
    for a in raw:
        vals = a.get("values") or []
        out[a.get("name", "")] = vals[0] if len(vals) == 1 else ", ".join(str(v) for v in vals)
    return out


def full_text(item: dict) -> str:
    a = attr_map(item.get("attributes", {}))
    return " ".join([
        item.get("description", ""),
        a.get("HEADING", ""),
        a.get("BODY_DYN", ""),
        a.get("BODY", ""),
    ])


def price_eur(item: dict) -> float | None:
    a = attr_map(item.get("attributes", {}))
    p = a.get("PRICE/AMOUNT") or a.get("PRICE")
    try:
        return float(str(p).replace(",", "."))
    except (TypeError, ValueError):
        return None


def listing_url(item: dict) -> str:
    a = attr_map(item.get("attributes", {}))
    seo = a.get("SEO_URL", "")
    if seo:
        return f"https://www.willhaben.at/iad/{seo}"
    ad_id = item.get("id", "")
    title = a.get("HEADING", item.get("description", "bike"))
    slug = re.sub(r"[^a-zA-Z0-9äöüÄÖÜß]+", "-", title.lower()).strip("-")[:80]
    return f"https://www.willhaben.at/iad/kaufen-und-verkaufen/d/gebraucht/{slug}-{ad_id}/"


def extract_years(text: str) -> list[int]:
    t = text.lower()
    years: list[int] = []
    for m in re.finditer(
        r"(?:baujahr|modelljahr|model\s*year|modell\s*20|my)\s*[:\s]?\s*(20\d{2})",
        t,
    ):
        years.append(int(m.group(1)))
    for m in re.finditer(r"(?:,\s*modell\s*|modelljahr\s*)(20\d{2})", t):
        years.append(int(m.group(1)))
    for m in re.finditer(r"\b(20(?:1[89]|2[0-5]))\b", text):
        years.append(int(m.group(1)))
    return years


def model_year(text: str) -> int | None:
    years = extract_years(text)
    if not years:
        return None
    # Prefer explicit model-year phrases over random numbers in dates/prices
    t = text.lower()
    explicit: list[int] = []
    for m in re.finditer(
        r"(?:baujahr|modelljahr|model\s*year|modell\s*20|my)\s*[:\s]?\s*(20\d{2})",
        t,
    ):
        explicit.append(int(m.group(1)))
    if explicit:
        return max(explicit)
    return max(y for y in years if 2015 <= y <= 2025)


def is_vintage_or_wrong_category(text: str) -> tuple[bool, str]:
    t = text.lower()
    bad = [
        "hardtail", "hard tail", " stoic ", "chisel", " gravel", "gravelbike", "e-bike", "e bike", "ebike",
        "pedelec", "kinder", "kinderrad", "damen fully", "damen mtb", "downhill only",
        "retro", "vintage", "90er", "80er", "klassiker", "sammler", "oldtimer",
        "cross country", " xc ", "marathonbike", "rennrad", "fatbike", "fat bike",
        "klapprad", "bmx", "trial bike", "dirt jump",
    ]
    for kw in bad:
        if kw in t:
            return True, kw.strip()
    if re.search(r"\bht\b", t) and "fully" not in t and "fsr" not in t:
        return True, "hardtail (HT)"
    return False, ""


def is_full_suspension(text: str) -> bool:
    t = text.lower()
    if any(x in t for x in ("hardtail", "hard tail", "nur hardtail")):
        return False
    signals = [
        "fully", "full suspension", "full-suspension", "fsr", "hinterbau",
        "hinterradfederung", "dämpfer", "daempfer", "schwinge", "federweg",
        "rear shock", "float x", "float dps", "super deluxe",
    ]
    if any(s in t for s in signals):
        return True
    models = [
        "fuel ex", "stumpjumper", "spectral", "stereo 1", "stereo 12", "stereo 13",
        "stereo 14", "stereo 15", "stereo 16", "capra", "jeffsy", "altitude",
        "sight", "nomad", "bronson", "hightower", "process 13", "process 134",
        "ripmo", "ralleon", "neuron", "strive", "meta tr", "meta am", "meta ht",
        "propain tyee", "transition", "enduro ", "slash", "remedy", "fox 36",
        "scott genius", "spark 9", "canyon spectral", "yt decoy", "commencal",
        "pivot trail", "pivot mach", "norco sight", "norco fluid", "bmc speedfox",
        "ghost riot", "ghost lector fs", "focus jam", "focus sam", "merida one",
        "cannondale habit", "cannondale jekyll", "trek fuel", "specialized enduro",
    ]
    return any(m in t for m in models)


def extract_travel_mm(text: str) -> list[int]:
    t = text.lower()
    travels: list[int] = []
    for m in re.finditer(
        r"(\d{2,3})\s*(?:mm\s*)?(?:federweg|travel|federgabel|gabel)",
        t,
    ):
        travels.append(int(m.group(1)))
    for m in re.finditer(r"federweg\s*(?:vorne|hinten)?\s*[:\s]*(\d{2,3})", t):
        travels.append(int(m.group(1)))
    for m in re.finditer(r"(\d{2,3})\s*/\s*(\d{2,3})\s*mm", t):
        travels.extend([int(m.group(1)), int(m.group(2))])
    return travels


def is_trail_am_travel(text: str, travels: list[int]) -> tuple[bool, str]:
    if travels:
        ok = [t for t in travels if TRAVEL_MIN <= t <= TRAVEL_MAX]
        if ok:
            return True, f"{max(ok)}mm"
        low = [t for t in travels if t < TRAVEL_MIN]
        if low and not any(t >= TRAVEL_MIN for t in travels):
            return False, f"too short ({min(low)}mm)"
        high = [t for t in travels if t > TRAVEL_MAX]
        if high and not ok:
            return False, f"too long ({max(high)}mm)"

    t = text.lower()
    # explicit XC travel without trail context
    if re.search(r"\b(80|90|100|110|120)\s*mm\b", t):
        if not any(x in t for x in ("trail", "enduro", "all mountain", "all-mountain", "140", "150", "160")):
            return False, "XC travel"

    trail_kw = [
        "trail", "all mountain", "all-mountain", "allmountain", "enduro",
        "bikepark", "agile", "descender",
    ]
    trail_models = [
        "fuel ex", "spectral", "stereo 140", "stereo 150", "stereo 160", "stereo hpc",
        "capra", "jeffsy", "sight", "altitude", "stumpjumper", "slash", "remedy",
        "bronson", "hightower", "neuron", "strive", "ralleon", "ripmo", "process 13",
        "meta tr", "meta am", "propain tyee", "norco sight", "ghost riot", "focus jam",
        "cannondale habit", "merida one", "scott genius", "bmc speedfox", "pivot",
    ]
    if any(k in t for k in trail_kw) or any(m in t for m in trail_models):
        return True, "trail/AM model"
    return False, "travel unknown"


def frame_fit_183(text: str) -> tuple[str, str]:
    t = text.lower()
    if re.search(r"größe\s*xl|rahmen.*\bxl\b|size\s*xl|\b21\s*[\"']|\b22\s*[\"']", t):
        if not re.search(r"größe\s*l\b|gr\.?\s*l\b|\b19", t):
            return "unlikely", "XL"
    if re.search(r"größe\s*xs|größe\s*s\b|size\s*xs|\b15\s*[\"']|\b16\s*[\"']", t):
        if not re.search(r"größe\s*[ml]\b|\b17\s*[\"']|\b18\s*[\"']", t):
            return "unlikely", "S/XS"
    if re.search(r"größe\s*l\b|size\s*l\b|gr\.?\s*l\b|\b19[,.]?5\s*[\"']|\b58\s*cm", t):
        return "likely_fit", "L"
    if re.search(r"größe\s*m\b|size\s*m\b|gr\.?\s*m\b|\b17\s*[\"']|\b18\s*[\"']|\b56\s*cm", t):
        return "likely_fit", "M"
    if re.search(r"\bs3\b|\bs4\b", t):
        return "likely_fit", "Specialized S3/S4"
    return "unknown", "?"


def deal_score(text: str, price: float | None, year: int | None, fit: str) -> tuple[int, list[str]]:
    t = text.lower()
    score = 0
    notes: list[str] = []

    if year:
        if year >= 2022:
            score += 4
            notes.append(f"MY{year}")
        elif year >= 2020:
            score += 3
            notes.append(f"MY{year}")
        elif year >= MIN_YEAR:
            score += 1
            notes.append(f"MY{year}")
    else:
        score -= 1
        notes.append("year?")

    for kw, pts in [
        ("slx", 1), ("xt ", 2), ("x01", 2), ("fox 36", 2), ("fox factory", 3),
        ("rockshox", 1), ("carbon", 1), ("dropper", 1), ("rechnung", 2),
        ("neuwertig", 2), ("kaum gefahren", 2), ("wenig gefahren", 2),
    ]:
        if kw in t:
            score += pts
            notes.append(kw.strip())

    for kw in ("defekt", "unfall", "rahmenriss", "händler", "aktion", "shop"):
        if kw in t:
            score -= 3

    if "vb" in t:
        score += 1
        notes.append("VB")

    if price and price <= 1400:
        score += 2
        notes.append("good price")
    if price and price <= 1100:
        score += 2
        notes.append("steal?")

    if fit == "likely_fit":
        score += 3
    elif fit == "unlikely":
        score -= 10

    return score, notes


def main() -> None:
    with open(INP, encoding="utf-8") as f:
        items = json.load(f)

    print(f"Input: {len(items)} listings\n")

    passed: list[dict] = []
    rejected: dict[str, int] = {}

    for item in items:
        text = full_text(item)
        t = text.lower()

        bad, reason = is_vintage_or_wrong_category(text)
        if bad:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue

        if not is_full_suspension(text):
            rejected["not full-sus"] = rejected.get("not full-sus", 0) + 1
            continue

        travels = extract_travel_mm(text)
        ok_travel, travel_note = is_trail_am_travel(text, travels)
        if not ok_travel:
            rejected[f"travel: {travel_note}"] = rejected.get(f"travel: {travel_note}", 0) + 1
            continue

        price = price_eur(item)
        if price is not None and (price < PRICE_EUR_MIN or price > PRICE_EUR_MAX):
            rejected["over budget"] = rejected.get("over budget", 0) + 1
            continue

        year = filter_model_year(text)
        if year and year < MIN_YEAR:
            rejected[f"too old ({year})"] = rejected.get(f"too old ({year})", 0) + 1
            continue
        if year is None and re.search(r"\b(201[0-8])\b", text):
            rejected["likely old (year in text)"] = rejected.get("likely old (year in text)", 0) + 1
            continue

        fit, fit_reason = frame_fit_183(text)
        if fit == "unlikely":
            rejected["wrong size"] = rejected.get("wrong size", 0) + 1
            continue

        score, notes = deal_score(text, price, year, fit)
        a = attr_map(item.get("attributes", {}))

        passed.append({
            "id": item["id"],
            "title": a.get("HEADING", item.get("description", ""))[:120],
            "price": price,
            "year": year,
            "travel": travel_note,
            "fit": fit_reason,
            "location": f"{a.get('POSTCODE', '')} {a.get('LOCATION', '')}, {a.get('STATE', '')}",
            "score": score,
            "notes": notes,
            "url": listing_url(item),
            "snippet": text[:300].replace("\n", " "),
        })

    passed.sort(key=lambda x: (-x["score"], x["price"] or 9999))

    fit_first = [p for p in passed if p["fit"] in ("L", "M", "Specialized S3/S4")]
    unknown_size = [p for p in passed if p["fit"] == "?"]

    print("Rejected breakdown (top):")
    for k, v in sorted(rejected.items(), key=lambda x: -x[1])[:12]:
        print(f"  {v:4d}  {k}")
    print(f"\nPassed filters: {len(passed)}")
    print(f"  M/L confirmed: {len(fit_first)}")
    print(f"  size unknown:  {len(unknown_size)}\n")

    print("=== TOP TRAIL/AM FULLY (M/L, 2019+, ~150mm) — Austria ===\n")
    for e in fit_first[:20]:
        y = f"MY{e['year']}" if e["year"] else "year?"
        print(f"€{e['price']:.0f} | {y} | {e['travel']} | {e['fit']} | score {e['score']}")
        print(f"  {e['title']}")
        print(f"  {e['location']}")
        print(f"  {e['url']}")
        print()

    print("=== WORTH CHECKING (size not in ad) ===\n")
    for e in unknown_size[:8]:
        y = f"MY{e['year']}" if e["year"] else "year?"
        print(f"€{e['price']:.0f} | {y} | {e['travel']} | score {e['score']}")
        print(f"  {e['title']}")
        print(f"  {e['url']}")
        print()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"top": fit_first[:40], "check_size": unknown_size[:20], "all_passed": passed}, f, ensure_ascii=False, indent=2)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
