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


def extract_travel_w175(text: str) -> list[int]:
    """Suspension travel in mm — reads 'Federweg', and 'Gabel/Dämpfer … mm' too."""
    t = text.lower()
    vals: list[int] = []
    for m in re.finditer(
        r"(?:federweg|federung|travel|zdvih)\s*(?:vorne|hinten|vorder|hinter|v\.|h\.)?\s*[:=]?\s*(\d{2,3})\s*mm?",
        t,
    ):
        vals.append(int(m.group(1)))
    for m in re.finditer(r"(\d{2,3})\s*mm\s*(?:federweg|travel|zdvih)", t):
        vals.append(int(m.group(1)))
    # fork/shock context followed by "NNN mm" within a short window
    for m in re.finditer(
        r"(?:federgabel|gabel|fork|vorne|vorder|d[äa]mpfer|daempfer|shock|hinten|heck)"
        r"[^\n\r.|;]{0,40}?(\d{2,3})\s*mm",
        t,
    ):
        vals.append(int(m.group(1)))
    for m in re.finditer(r"(\d{2,3})\s*/\s*(\d{2,3})\s*mm", t):
        vals.extend([int(m.group(1)), int(m.group(2))])
    # plausible suspension travel only (excludes rotor 203, dropper aside)
    return [v for v in vals if 90 <= v <= 220]


def is_enduro_am_travel(text: str, travels: list[int]) -> tuple[bool, str]:
    """Prefer ~140-180 mm. If travel is stated but out of range → reject even if
    the ad says 'enduro'. Keyword/model fallback only when travel is unknown."""
    if travels:
        ok = [x for x in travels if TRAVEL_MIN <= x <= TRAVEL_MAX]
        if ok:
            return True, f"{max(ok)}mm"
        return False, f"travel {min(travels)}-{max(travels)}mm"

    t = text.lower()
    kw = ["enduro", "all mountain", "all-mountain", "allmountain", "bikepark", "freeride"]
    models = [
        "capra", "jeffsy", "spectral", "stereo 150", "stereo 160", "sight", "altitude",
        "nomad", "bronson", "meta am", "meta tr", "slash", "strive", "torque",
        "one-sixty", "one sixty", "propain tyee", "rallon", "ripmo", "sb150", "sb160",
        "megatower", "hightower", "firebird", "spindrift",
        "occam", "trance x",
    ]
    if any(k in t for k in kw) or any(m in t for m in models):
        return True, "enduro/AM"
    return False, "travel unknown"


# Frame-size label words (singular, word-boundaried so plural size charts like
# "FRAME SIZES XS S M L XL" don't leak every size).
_SIZE_LABEL = (
    r"(?:rahmengr[öo]ße|rahmengroesse|rahmenh[öo]he|gr[öo]ße|groesse|gr\.|"
    r"\bsize\b|\bvelikost\b|\bvel\.|\brh\b|\brám\b|\brahmen\b)"
)


def _size_from_cm(cm: int) -> str:
    if cm <= 37:
        return "xs"
    if cm <= 43:
        return "s"
    if cm <= 46:
        return "m"
    if cm <= 50:
        return "l"
    return "xl"


def _size_from_inch(inch: int) -> str:
    if inch <= 14:
        return "xs"
    if inch <= 16:
        return "s"
    if inch <= 18:
        return "m"
    if inch <= 20:
        return "l"
    return "xl"


def _size_letters(s: str) -> set[str]:
    s = s.lower()
    out: set[str] = set()
    for m in re.finditer(_SIZE_LABEL + r"\s*[:=\-]?\s*(xxl|xl|xs|s|m|l)\b", s):
        out.add(m.group(1))
    for m in re.finditer(r"[-_/]gr[-_]?(xs|s|m|l|xl)\b", s):
        out.add(m.group(1))
    for m in re.finditer(r"\bs([1-5])\b", s):
        out.add({"1": "xs", "2": "s", "3": "m", "4": "l", "5": "xl"}[m.group(1)])
    for m in re.finditer(_SIZE_LABEL + r"\s*[:=\-]?\s*(\d{2})\s*cm", s):
        out.add(_size_from_cm(int(m.group(1))))
    for m in re.finditer(r"\b(1[4-9]|2[0-2])(?:[.,]5)?\s*(?:zoll|\"|'')", s):
        out.add(_size_from_inch(int(m.group(1))))
    return {"xl" if x == "xxl" else x for x in out}


def frame_fit_w175(text: str, title: str = "") -> tuple[str, str]:
    """Fit for ~175 cm (or a bit less) → S/M. L/XL too big, XS too small.

    Presence of a confirmed S/M wins; otherwise a confirmed L/XL rejects. A bare
    size letter at the end of the title (e.g. "... 8.0 L") is also honoured.
    """
    letters = _size_letters(text)

    tl = title.lower().strip()
    mt = re.search(r"(?:^|[\s\-/(])(xxl|xl|xs|[sml])\)?\s*$", tl)
    if mt:
        letters.add("xl" if mt.group(1) == "xxl" else mt.group(1))

    good = letters & {"s", "m"}
    big = letters & {"l", "xl"}

    if good:
        return "likely_fit", "M" if "m" in good else "S"
    if big:
        return "unlikely", "XL" if "xl" in big else "L (too big)"
    if "xs" in letters:
        return "unlikely", "XS (too small)"
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


def evaluate(text: str, price_eur: float | None, title: str = "") -> dict | None:
    bad, _ = is_vintage_or_wrong_category(text)
    if bad:
        return None
    if not is_full_suspension(text):
        return None

    travels = extract_travel_w175(text)
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

    fit_class, fit_label = frame_fit_w175(text, title)
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
        meta = evaluate(text, price, item.get("title", ""))
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
        a = attr_map(item.get("attributes", {}))
        meta = evaluate(text, price, a.get("HEADING", item.get("description", "")))
        if not meta:
            continue
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
