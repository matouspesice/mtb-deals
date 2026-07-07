"""Merge & rank deals from all sources into one report."""
from __future__ import annotations

import json
from pathlib import Path

from analyze_generic import analyze
from export_report import export as export_report
from filters import PRICE_EUR_MAX, PRICE_EUR_MIN

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "merged_deals.json"

AT_SOURCES = {"willhaben.at", "radbazar.at", "radlmarkt.at", "biklo.at"}
CZ_SOURCES = {"bazos.cz", "sbazar.cz", "cyklobazar.cz", "biklo.cz"}
MARKET_SOURCES = {"buycycle.com", "bikefair.org"}


def source_key(name: str) -> str:
    return (name or "").split(" (")[0]

SOURCES = {
    "willhaben.at": DATA / "at_trail_deals.json",
    "bazos.cz": DATA / "bazos_deals.json",
    "sbazar.cz": DATA / "sbazar_deals.json",
    "cyklobazar.cz": DATA / "cyklobazar_deals.json",
    "radbazar.at": DATA / "radbazar_deals.json",
    "radlmarkt.at": DATA / "radlmarkt_deals.json",
    "biklo.at": DATA / "biklo_deals.json",
    "biklo.cz": DATA / "biklo_deals.json",
    "buycycle.com": DATA / "buycycle_listings.json",
    "bikefair.org": DATA / "bikefair_listings.json",
}

PIN_URL_FRAGMENTS = (
    "trek-remedy-8-bj-2021",
    "878192628",
    "mtb-focus-jam-6-9-1231437189",
    "1231437189",
)


def in_budget(e: dict) -> bool:
    p = e.get("price_eur")
    if p is None:
        return True
    return PRICE_EUR_MIN <= p <= PRICE_EUR_MAX


def willhaben_entry(e: dict) -> dict:
    return {
        "source": "willhaben.at",
        "title": e.get("title", ""),
        "price_eur": e.get("price") or e.get("price_eur"),
        "year": e.get("year"),
        "travel": e.get("travel"),
        "fit": e.get("fit"),
        "location": e.get("location", ""),
        "score": e.get("score", 0),
        "notes": e.get("notes", []),
        "url": e.get("url", ""),
    }


def load_willhaben() -> tuple[list[dict], list[dict]]:
    p = SOURCES["willhaben.at"]
    if not p.exists():
        return [], []
    d = json.load(open(p, encoding="utf-8"))
    items = d.get("top", d.get("best_fit", []))
    all_items = d.get("all_passed", items)
    out = [willhaben_entry(e) for e in items]
    seen_urls: set[str] = set()
    pinned: list[dict] = []
    for e in all_items:
        url = e.get("url") or ""
        if url in seen_urls:
            continue
        if any(p in url for p in PIN_URL_FRAGMENTS):
            seen_urls.add(url)
            pinned.append(willhaben_entry(e))
    return out, pinned


def load_bazos() -> list[dict]:
    p = SOURCES["bazos.cz"]
    if not p.exists():
        return []
    d = json.load(open(p, encoding="utf-8"))
    items = d.get("all", d.get("top", d.get("best_fit", [])))
    return [{**e, "source": "bazos.cz"} for e in items]


def load_analyzed_listings(key: str) -> list[dict]:
    if key == "sbazar.cz":
        deals = DATA / "sbazar_deals.json"
    elif key == "cyklobazar.cz":
        deals = DATA / "cyklobazar_deals.json"
    elif key == "radbazar.at":
        deals = DATA / "radbazar_deals.json"
    elif key == "radlmarkt.at":
        deals = DATA / "radlmarkt_deals.json"
    elif key in ("biklo.at", "biklo.cz"):
        deals = DATA / "biklo_deals.json"
    elif key == "buycycle.com":
        deals = DATA / "buycycle_deals.json"
    elif key == "bikefair.org":
        deals = DATA / "bikefair_deals.json"
    else:
        deals = DATA / f"{key.replace('.org', '').replace('.com', '')}_deals.json"
    if deals.exists():
        d = json.load(open(deals, encoding="utf-8"))
        return d.get("all", d.get("top", []))
    p = SOURCES[key]
    if not p.exists():
        return []
    items = json.load(open(p, encoding="utf-8"))
    if isinstance(items, dict):
        return items.get("top", [])
    return analyze(items, key)


def normalize_fit(items: list[dict]) -> list[dict]:
    fit_ok: list[dict] = []
    for m in items:
        fit = m.get("fit")
        if fit == "?":
            fit = "size?"
            m["fit"] = fit
        m_ok = fit in ("L", "M", "S3/S4", "Specialized S3/S4") or m.get("fit_class") == "likely_fit"
        size_unknown_ok = fit == "size?" and m.get("score", 0) >= 9
        if (m_ok or size_unknown_ok) and in_budget(m):
            fit_ok.append(m)
    return fit_ok


def print_section(title: str, items: list[dict], limit: int = 15) -> None:
    print(f"=== {title} ===\n")
    if not items:
        print("  (žádné)\n")
        return
    for e in items[:limit]:
        pe = f"€{e['price_eur']:.0f}" if e.get("price_eur") else "?"
        yr = f"MY{e['year']}" if e.get("year") else ""
        print(f"{pe} | {yr} | {e.get('travel', '')} | {e.get('fit', '')} | score {e.get('score', 0)} | [{e.get('source')}]")
        print(f"  {e.get('title', '')[:90]}")
        if e.get("location"):
            print(f"  {e['location']}")
        print(f"  {e['url']}")
        print()


def main() -> None:
    merged: list[dict] = []
    wh_items, wh_pinned = load_willhaben()
    merged.extend(wh_items)
    merged.extend(load_bazos())
    merged.extend(load_analyzed_listings("sbazar.cz"))
    merged.extend(load_analyzed_listings("cyklobazar.cz"))
    merged.extend(load_analyzed_listings("radbazar.at"))
    merged.extend(load_analyzed_listings("radlmarkt.at"))
    merged.extend(load_analyzed_listings("biklo.at"))
    merged.extend(load_analyzed_listings("buycycle.com"))
    merged.extend(load_analyzed_listings("bikefair.org"))

    fit_ok = normalize_fit(merged)
    fit_ok.sort(key=lambda x: (-x.get("score", 0), x.get("price_eur") or 9999))

    pinned = wh_pinned or [m for m in fit_ok if any(p in (m.get("url") or "") for p in PIN_URL_FRAGMENTS)]
    fit_urls = {m.get("url") for m in fit_ok if m.get("url")}
    for p in pinned:
        if p.get("url") and p["url"] not in fit_urls:
            fit_ok.append(p)
            fit_urls.add(p["url"])
    fit_ok.sort(key=lambda x: (-x.get("score", 0), x.get("price_eur") or 9999))
    at_deals = [m for m in fit_ok if source_key(m.get("source", "")) in AT_SOURCES and m not in pinned]
    cz_deals = [m for m in fit_ok if source_key(m.get("source", "")) in CZ_SOURCES]
    market_deals = [m for m in fit_ok if source_key(m.get("source", "")) in MARKET_SOURCES]

    by_src: dict[str, int] = {}
    for m in fit_ok:
        sk = source_key(m.get("source", "?"))
        by_src[sk] = by_src.get(sk, 0) + 1

    print(f"=== MERGED TRAIL/AM DEALS (€{PRICE_EUR_MIN:.0f}–{PRICE_EUR_MAX:.0f}, M/L, 2019+) ===\n")
    print("Counts by source:", by_src)
    print(f"Total ranked: {len(fit_ok)}")
    print(f"AT (willhaben): {len(at_deals)} | CZ (bazos+sbazar): {len([m for m in cz_deals if m.get('source') in CZ_SOURCES])} | marketplaces: {len(market_deals)}\n")

    if pinned:
        print_section("TVŮJ VÝBĚR", pinned, limit=3)

    print_section(f"TOP RAKOUSKO (willhaben) — {len(at_deals)} inzerátů", at_deals, limit=15)
    print_section(f"ČESKO (bazos + sbazar) — {len(cz_deals)} inzerátů", cz_deals, limit=8)
    print_section("EU MARKETPLACES (buycycle, bikefair)", market_deals, limit=8)

    report = {
        "price_max_eur": PRICE_EUR_MAX,
        "by_source": by_src,
        "pinned": pinned,
        "top_at": at_deals[:30],
        "top_cz": cz_deals[:20],
        "top_market": market_deals[:20],
        "top": fit_ok[:50],
        "all": fit_ok,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    html_path, txt_path = export_report(report)
    print(f"Saved {OUT}")
    print(f"Report HTML: {html_path}")
    print(f"Report text: {txt_path}")


if __name__ == "__main__":
    main()
