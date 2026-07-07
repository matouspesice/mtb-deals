"""Build a second search profile: enduro/all-mountain (~150-170 mm) for a
shorter rider (~175 cm or a bit less) → frame sizes S/M.

Re-analyzes the SAME raw scraped listings as the 183 cm pipeline, but with a
different frame-fit heuristic and a travel band centered on ~160 mm. Output is a
separate report so the 183 cm report stays untouched:

    data/merged_deals_w175.json
    data/report_women175.html
    data/report_women175.txt

Run:
    python mtb/scripts/build_women175.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from analyze_trail import attr_map, full_text, listing_url
from analyze_trail import price_eur as wh_price_eur
from export_report import export as export_report
from filters import (
    MIN_YEAR,
    PRICE_EUR_MAX,
    czk_to_eur,
    extract_travel_mm,
    is_full_suspension,
    is_vintage_or_wrong_category,
    model_year,
)
from linkcheck import filter_live

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT_JSON = DATA / "merged_deals_w175.json"
OUT_HTML = DATA / "report_women175.html"
OUT_TXT = DATA / "report_women175.txt"

# Enduro / all-mountain around 160 mm — still pedalable uphill.
TRAVEL_MIN = 140
TRAVEL_MAX = 180

# This profile starts a bit cheaper than the 183 cm search.
PRICE_EUR_MIN = 600

AT_SOURCES = {"willhaben.at", "radbazar.at", "radlmarkt.at", "biklo.at"}
CZ_SOURCES = {"bazos.cz", "sbazar.cz", "cyklobazar.cz", "biklo.cz"}

GENERIC_SOURCES = {
    "bazos.cz": DATA / "bazos_listings.json",
    "sbazar.cz": DATA / "sbazar_listings.json",
    "cyklobazar.cz": DATA / "cyklobazar_listings.json",
    "radbazar.at": DATA / "radbazar_listings.json",
    "radlmarkt.at": DATA / "radlmarkt_listings.json",
    "biklo.at": DATA / "biklo_listings.json",
    "buycycle.com": DATA / "buycycle_listings.json",
    "bikefair.org": DATA / "bikefair_listings.json",
}


def is_enduro_am_travel(text: str, travels: list[int]) -> tuple[bool, str]:
    """Prefer ~140-180 mm; keyword/model fallback when travel not stated."""
    if travels:
        ok = [x for x in travels if TRAVEL_MIN <= x <= TRAVEL_MAX]
        if ok:
            return True, f"{max(ok)}mm"
        if all(x < TRAVEL_MIN for x in travels):
            return False, f"too short ({max(travels)}mm)"
        if all(x > TRAVEL_MAX for x in travels):
            return False, f"too long ({min(travels)}mm)"

    t = text.lower()
    if re.search(r"\b(80|90|100|110|120|130)\s*mm\b", t):
        if not any(x in t for x in ("enduro", "all mountain", "all-mountain", "140", "150", "160", "170")):
            return False, "XC/trail travel"

    kw = ["enduro", "all mountain", "all-mountain", "allmountain", "bikepark", "freeride"]
    models = [
        "capra", "jeffsy", "spectral", "stereo 150", "stereo 160", "sight", "altitude",
        "nomad", "bronson", "meta am", "meta tr", "slash", "strive", "torque",
        "one-sixty", "one sixty", "propain tyee", "rallon", "ripmo", "sb150", "sb160",
        "megatower", "hightower", "firebird", "sam", "reign", "enduro ", "spindrift",
        "occam", "rise", "rocky mountain instinct", "instinct", "trance x",
    ]
    if any(k in t for k in kw) or any(m in t for m in models):
        return True, "enduro/AM"
    return False, "travel unknown"


def frame_fit_w175(text: str) -> tuple[str, str]:
    """Fit for ~175 cm (or a bit less) → S/M. L and XL are too big, XS too small."""
    t = text.lower()

    too_big = re.search(
        r"gr(?:öße|oesse|\.)?\s*xl|size\s*xl|velikost\s*xl|ram\s*xl|\bxl\b"
        r"|\b2[0-2]\s*[\"'zZ]|\b5[0-9]\s*cm|\b6[0-9]\s*cm|\bs5\b",
        t,
    )
    if too_big and not re.search(r"gr(?:öße|oesse|\.)?\s*[sm]\b|size\s*[sm]\b|velikost\s*[sm]\b", t):
        return "unlikely", "XL"

    is_large = re.search(
        r"gr(?:öße|oesse|\.)?\s*l\b|size\s*l\b|velikost\s*l\b|gr\.?\s*l\b"
        r"|[-_/]gr[-_]?l[a-z0-9]*|\b19[,.]?5?\s*[\"'zZ]|\b48\s*cm|\b50\s*cm|\bs4\b",
        t,
    )
    if is_large and not re.search(r"gr(?:öße|oesse|\.)?\s*[sm]\b|size\s*[sm]\b|velikost\s*[sm]\b", t):
        return "unlikely", "L (too big)"

    too_small = re.search(
        r"gr(?:öße|oesse|\.)?\s*xs|size\s*xs|velikost\s*xs|\b1[34]\s*[\"'zZ]|\b3[0-8]\s*cm|\bs1\b",
        t,
    )
    if too_small and not re.search(r"gr(?:öße|oesse|\.)?\s*[sm]\b|size\s*[sm]\b|velikost\s*[sm]\b", t):
        return "unlikely", "XS (too small)"

    if re.search(
        r"gr(?:öße|oesse|\.)?\s*m\b|size\s*m\b|velikost\s*m\b|gr\.?\s*m\b"
        r"|[-_/]gr[-_]?m[a-z0-9]*|\b1[78]\s*[\"'zZ]|\b4[46]\s*cm|\bs3\b",
        t,
    ):
        return "likely_fit", "M"
    if re.search(
        r"gr(?:öße|oesse|\.)?\s*s\b|size\s*s\b|velikost\s*s\b|gr\.?\s*s\b"
        r"|[-_/]gr[-_]?s[a-z0-9]*|\b1[56]\s*[\"'zZ]|\b4[02]\s*cm|\bs2\b",
        t,
    ):
        return "likely_fit", "S"
    return "unknown", "?"


def score_w175(text: str, price_eur: float | None, year: int | None, fit_class: str) -> tuple[int, list[str]]:
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
        ("slx", 1), ("xt ", 2), ("x01", 2), ("gx ", 1), ("fox 36", 2), ("fox 38", 2),
        ("fox factory", 3), ("zeb", 2), ("lyrik", 2), ("carbon", 1), ("dropper", 1),
        ("reverb", 1), ("teleskop", 1), ("rechnung", 2), ("faktura", 1), ("neuwertig", 2),
        ("nové", 1), ("nove", 1), ("kaum gefahren", 2), ("málo najeto", 1),
    ]:
        if kw in t:
            score += pts
            notes.append(kw.strip())

    # Enduro / all-mountain / bikepark intent the rider asked for.
    for kw in ("enduro", "all mountain", "all-mountain", "allmountain", "bikepark", "flow"):
        if kw in t:
            score += 1
            notes.append("enduro/AM")
            break

    # Small-frame / women's build bonus.
    for kw in ("damen", "frauen", "women", "wsd", "ladies", "dámské", "damske", "dievča", "holka"):
        if kw in t:
            score += 2
            notes.append("women/small")
            break

    if "vb" in t or "dohodou" in t or "smlouvou" in t:
        score += 1
        notes.append("VB")
    if price_eur and price_eur <= 1400:
        score += 2
        notes.append("good price")
    if price_eur and price_eur <= 1100:
        score += 2
        notes.append("steal?")

    if fit_class == "likely_fit":
        score += 3
    elif fit_class == "unlikely":
        score -= 10

    return score, notes


def evaluate(text: str, price_eur: float | None) -> dict | None:
    bad, _ = is_vintage_or_wrong_category(text)
    if bad:
        return None
    if not is_full_suspension(text):
        return None

    travels = extract_travel_mm(text)
    ok_travel, travel_note = is_enduro_am_travel(text, travels)
    if not ok_travel:
        return None

    if price_eur is not None and (price_eur < PRICE_EUR_MIN or price_eur > PRICE_EUR_MAX):
        return None

    year = model_year(text)
    if year and year < MIN_YEAR:
        return None
    if year is None and re.search(r"\b(201[0-8])\b", text):
        return None

    fit_class, fit_label = frame_fit_w175(text)
    if fit_class == "unlikely":
        return None

    score, notes = score_w175(text, price_eur, year, fit_class)
    return {
        "year": year,
        "travel": travel_note,
        "fit": fit_label,
        "fit_class": fit_class,
        "score": score,
        "notes": notes,
    }


def from_generic(source: str, path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for item in json.load(open(path, encoding="utf-8")):
        text = " ".join([
            item.get("title", ""),
            item.get("description", ""),
            item.get("body", ""),
        ])
        price = item.get("price_eur")
        if price is None and item.get("price_czk"):
            price = czk_to_eur(item["price_czk"])
        meta = evaluate(text, price)
        if not meta:
            continue
        out.append({
            "source": item.get("source", source),
            "id": item.get("id"),
            "title": (item.get("title", "") or "")[:120],
            "price_eur": price,
            "price_czk": item.get("price_czk"),
            "location": item.get("location", ""),
            "url": item.get("url", ""),
            "image_url": item.get("image_url"),
            **meta,
        })
    return out


def from_willhaben() -> list[dict]:
    p = DATA / "at_listings.json"
    if not p.exists():
        return []
    out: list[dict] = []
    for item in json.load(open(p, encoding="utf-8")):
        text = full_text(item)
        price = wh_price_eur(item)
        meta = evaluate(text, price)
        if not meta:
            continue
        a = attr_map(item.get("attributes", {}))
        out.append({
            "source": "willhaben.at",
            "id": item.get("id"),
            "title": (a.get("HEADING", item.get("description", "")) or "")[:120],
            "price_eur": price,
            "location": f"{a.get('POSTCODE', '')} {a.get('LOCATION', '')}, {a.get('STATE', '')}".strip(", "),
            "url": listing_url(item),
            **meta,
        })
    return out


def source_key(name: str) -> str:
    return (name or "").split(" (")[0]


def main() -> None:
    merged: list[dict] = []
    merged.extend(from_willhaben())
    for src, path in GENERIC_SOURCES.items():
        merged.extend(from_generic(src, path))

    # Keep confirmed S/M fits, plus strong unknown-size candidates worth a look.
    kept: list[dict] = []
    seen: set[str] = set()
    for m in merged:
        url = m.get("url") or ""
        if url and url in seen:
            continue
        fit_ok = m.get("fit_class") == "likely_fit"
        unknown_ok = m.get("fit") == "?" and m.get("score", 0) >= 8
        if fit_ok or unknown_ok:
            if url:
                seen.add(url)
            kept.append(m)

    if "--no-verify" not in sys.argv:
        print(f"Verifying {len(kept)} links (dropping sold/expired ads)...")
        kept, dropped = filter_live(kept)
        print(f"  dropped {dropped} dead links, {len(kept)} live remain")

    kept.sort(key=lambda x: (-x.get("score", 0), x.get("price_eur") or 9999))

    by_src: dict[str, int] = {}
    for m in kept:
        sk = source_key(m.get("source", "?"))
        by_src[sk] = by_src.get(sk, 0) + 1

    at_deals = [m for m in kept if source_key(m.get("source", "")) in AT_SOURCES]
    cz_deals = [m for m in kept if source_key(m.get("source", "")) in CZ_SOURCES]

    report = {
        "page_title": "MTB enduro/AM pro ~175 cm — report",
        "heading": "MTB enduro / all-mountain — ~175 cm (S/M)",
        "fit_label": "S/M",
        "price_min_eur": PRICE_EUR_MIN,
        "price_max_eur": PRICE_EUR_MAX,
        "by_source": by_src,
        "pinned": [],
        "top_at": at_deals[:30],
        "top_cz": cz_deals[:20],
        "top_market": [],
        "top": kept[:50],
        "all": kept,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    html_path, txt_path = export_report(report, html_out=OUT_HTML, txt_out=OUT_TXT)

    print(f"Enduro/AM ~175 cm (S/M), €{PRICE_EUR_MIN:.0f}-{PRICE_EUR_MAX:.0f}, {TRAVEL_MIN}-{TRAVEL_MAX} mm")
    print("Counts by source:", by_src)
    print(f"Total kept: {len(kept)}  (AT {len(at_deals)} | CZ {len(cz_deals)})")
    print(f"Saved {OUT_JSON}")
    print(f"Report HTML: {html_path}")
    print(f"Report text: {txt_path}")


if __name__ == "__main__":
    main()
