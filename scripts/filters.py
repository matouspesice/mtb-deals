"""Shared bike listing filters — trail/AM fully, 2019+, M/L for ~183 cm."""
from __future__ import annotations

import re

MIN_YEAR = 2019
TRAVEL_MIN = 130
TRAVEL_MAX = 170

# 800–1900 EUR ≈ 20 000–47 500 CZK
CZK_PER_EUR = 25.0
PRICE_EUR_MIN = 800
PRICE_EUR_MAX = 1900


def eur_to_czk(eur: float) -> int:
    return int(eur * CZK_PER_EUR)


def czk_to_eur(czk: float) -> float:
    return czk / CZK_PER_EUR


def extract_years(text: str) -> list[int]:
    t = text.lower()
    years: list[int] = []
    for m in re.finditer(
        r"(?:baujahr|modelljahr|model\s*year|modell\s*20|my|model)\s*[:\s]?\s*(20\d{2})",
        t,
    ):
        years.append(int(m.group(1)))
    for m in re.finditer(r"\b(20(?:1[89]|2[0-5]))\b", text):
        years.append(int(m.group(1)))
    return years


def model_year(text: str) -> int | None:
    t = text.lower()
    explicit: list[int] = []
    for m in re.finditer(
        r"(?:baujahr|bj\.?|modelljahr|model\s*year|modell\s*20|my|model|rok\s*výroby|vyrobeno)\s*[:\s]?\s*(20\d{2})",
        t,
    ):
        explicit.append(int(m.group(1)))
    if explicit:
        return max(explicit)
    years = extract_years(text)
    if not years:
        return None
    # Ignore recent service / purchase dates (e.g. "Ende 2025 serviciert")
    service_ctx = re.compile(
        r"(?:servic|servis|gekauft|pořízen|zakoupen|koupen|novemb|dezemb|januar|únor|brezen|"
        r"březen|duben|květen|červen|červenec|srpen|září|říjen|listopad|prosinec)\s*(?:\d{1,2}\.?)?\s*(20\d{2})",
        re.I,
    )
    filtered = [y for y in years if not service_ctx.search(t) or y != max(years)]
    if not filtered:
        filtered = [y for y in years if y <= 2024] or years
    return max(y for y in filtered if 2015 <= y <= 2025)


def is_vintage_or_wrong_category(text: str) -> tuple[bool, str]:
    t = text.lower()
    bad = [
        "hardtail", "hard tail", " ht ", " stoic ", "chisel", " gravel", "gravelbike",
        "e-bike", "e bike", "ebike", "elektro", "pedelec", "macina", "kapoho", "bosch motor",
        "kinder", "kinderrad",
        "dětské", "detske", "damen fully", "downhill only", "retro", "vintage",
        "90er", "80er", "klassiker", "sammler", " cross country", " xc ", "marathonbike",
        "rennrad", "fatbike", "bmx", "skládač", "skladacka", "koloběž", "kolobez",
    ]
    for kw in bad:
        if kw in t:
            return True, kw.strip()
    return False, ""


def is_full_suspension(text: str) -> bool:
    t = text.lower()
    if any(x in t for x in ("hardtail", "hard tail", "hardtailové", "jen hardtail")):
        return False
    signals = [
        "fully", "full suspension", "full-suspension", "fsr", "celoodpružen", "celoodpruzen",
        "hinterbau", "dämpfer", "daempfer", "zadní tlumič", "zadni tlumic", "federweg",
        "schwinge", "fs3", " fs ", " rear shock",
    ]
    if any(s in t for s in signals):
        return True
    models = [
        "fuel ex", "stumpjumper", "spectral", "stereo 1", "capra", "jeffsy", "altitude",
        "sight", "nomad", "bronson", "process 134", "process 13", "ripmo", "neuron",
        "strive", "meta tr", "meta am", "slash", "remedy", "fluid fs", "norco fluid",
        "one-sixty", "one sixty", "one-forty", "one forty", "one-twenty", "genius",
        "focus jam", "habit", "merida one", "kona process", "radon skeen", "radon jab",
    ]
    return any(m in t for m in models)


def extract_travel_mm(text: str) -> list[int]:
    t = text.lower()
    travels: list[int] = []
    for m in re.finditer(
        r"(\d{2,3})\s*(?:mm\s*)?(?:federweg|travel|zdvihem|zdviž|zdvih)",
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
        ok = [x for x in travels if TRAVEL_MIN <= x <= TRAVEL_MAX]
        if ok:
            return True, f"{max(ok)}mm"
        if all(x < TRAVEL_MIN for x in travels):
            return False, f"too short ({max(travels)}mm)"
        if all(x > TRAVEL_MAX for x in travels):
            return False, f"too long ({min(travels)}mm)"

    t = text.lower()
    if re.search(r"\b(80|90|100|110|120)\s*mm\b", t):
        if not any(x in t for x in ("trail", "enduro", "140", "150", "160")):
            return False, "XC travel"

    trail_kw = ["trail", "all mountain", "all-mountain", "enduro", "bikepark"]
    trail_models = [
        "fuel ex", "spectral", "stereo 140", "stereo 150", "stereo 160", "capra",
        "jeffsy", "sight", "altitude", "stumpjumper", "slash", "remedy", "bronson",
        "neuron", "strive", "process 134", "meta tr", "fluid fs", "one-sixty",
        "one-forty", "focus jam", "habit", "genius", "kona process", "norco fluid",
    ]
    if any(k in t for k in trail_kw) or any(m in t for m in trail_models):
        return True, "trail/AM"
    return False, "travel unknown"


def frame_fit_183(text: str) -> tuple[str, str]:
    t = text.lower()
    if re.search(r"velikost\s*xl|größe\s*xl|size\s*xl|\b21\s*[\"']|\b22\s*[\"']|ram\s*xl", t):
        if not re.search(r"velikost\s*l|größe\s*l|\b19", t):
            return "unlikely", "XL"
    if re.search(r"velikost\s*s\b|größe\s*s\b|size\s*xs|\b15\s*[\"']|\b16\s*[\"']|ram\s*s\b", t):
        if not re.search(r"velikost\s*[ml]|größe\s*[ml]|\b17|\b18", t):
            return "unlikely", "S/XS"
    if re.search(
        r"velikost\s*l\b|größe\s*l\b|size\s*l\b|gr\.?\s*l\b|\b19[,.]?5|\b58\s*cm"
        r"|[-_/]gr[-_]l[a-z0-9]*|[-_]l[-_]|\bsize\s*l\b",
        t,
    ):
        return "likely_fit", "L"
    if re.search(
        r"velikost\s*m\b|größe\s*m\b|size\s*m\b|gr\.?\s*m\b|\b17\s*[\"']|\b18\s*[\"']|\b56\s*cm"
        r"|[-_/]gr[-_]m[a-z0-9]*|[-_]m[-_]|\bsize\s*m\b",
        t,
    ):
        return "likely_fit", "M"
    if re.search(r"\bs3\b|\bs4\b", t):
        return "likely_fit", "S3/S4"
    return "unknown", "?"


def deal_score(text: str, price_eur: float | None, year: int | None, fit: str) -> tuple[int, list[str]]:
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
        ("carbon", 1), ("dropper", 1), ("rechnung", 2), ("faktura", 1),
        ("neuwertig", 2), ("nové", 1), ("nove", 1), ("kaum gefahren", 2), ("málo najeto", 1),
    ]:
        if kw in t:
            score += pts
            notes.append(kw.strip())

    if "vb" in t or "dohodou" in t or "smlouvou" in t:
        score += 1
        notes.append("VB")

    if price_eur and price_eur <= 1400:
        score += 2
        notes.append("good price")
    if price_eur and price_eur <= 1100:
        score += 2
        notes.append("steal?")

    if fit == "likely_fit":
        score += 3
    elif fit == "unlikely":
        score -= 10

    return score, notes


def passes_trail_filters(text: str) -> tuple[bool, str, dict]:
    """Return (ok, reject_reason, meta)."""
    bad, reason = is_vintage_or_wrong_category(text)
    if bad:
        return False, reason, {}

    if not is_full_suspension(text):
        return False, "not full-sus", {}

    travels = extract_travel_mm(text)
    ok_travel, travel_note = is_trail_am_travel(text, travels)
    if not ok_travel:
        return False, f"travel: {travel_note}", {}

    year = model_year(text)
    if year and year < MIN_YEAR:
        return False, f"too old ({year})", {}
    if year is None and re.search(r"\b(201[0-8])\b", text):
        return False, "likely old", {}

    fit, fit_reason = frame_fit_183(text)
    if fit == "unlikely":
        return False, "wrong size", {}

    return True, "", {
        "year": year,
        "travel": travel_note,
        "fit": fit_reason,
        "fit_class": fit,
    }
