"""Analyze normalized listings JSON from any source using shared filters."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from filters import PRICE_EUR_MAX, PRICE_EUR_MIN, czk_to_eur, deal_score, passes_trail_filters

ROOT = Path(__file__).resolve().parent.parent


def analyze(items: list[dict], source_name: str) -> list[dict]:
    passed: list[dict] = []
    for item in items:
        text = " ".join([
            item.get("title", ""),
            item.get("description", ""),
            item.get("body", ""),
        ])
        ok, reason, meta = passes_trail_filters(text)
        if not ok:
            continue

        price_eur = item.get("price_eur")
        if price_eur is None and item.get("price_czk"):
            price_eur = czk_to_eur(item["price_czk"])
        if price_eur is not None and (price_eur < PRICE_EUR_MIN or price_eur > PRICE_EUR_MAX):
            continue

        score, notes = deal_score(text, price_eur, meta.get("year"), meta.get("fit_class", "unknown"))
        passed.append({
            "source": item.get("source", source_name),
            "id": item.get("id"),
            "title": item.get("title", "")[:120],
            "price_eur": price_eur,
            "price_czk": item.get("price_czk"),
            "year": meta.get("year"),
            "travel": meta.get("travel"),
            "fit": meta.get("fit"),
            "location": item.get("location", ""),
            "score": score,
            "notes": notes,
            "url": item.get("url", ""),
            "snippet": text[:280].replace("\n", " "),
        })

    passed.sort(key=lambda x: (-x["score"], x["price_eur"] or 9999))
    return passed


def main() -> None:
    inp = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "bazos_listings.json"
    out = inp.with_name(inp.stem.replace("_listings", "_deals") + ".json")
    if out == inp:
        out = ROOT / "data" / f"{inp.stem}_deals.json"

    items = json.load(open(inp, encoding="utf-8"))
    results = analyze(items, inp.stem)
    fit = [r for r in results if r["fit"] in ("L", "M", "S3/S4")]

    print(f"{inp.name}: {len(items)} in -> {len(results)} passed -> {len(fit)} M/L\n")
    for e in fit[:15]:
        pe = f"€{e['price_eur']:.0f}" if e["price_eur"] else "?"
        print(f"{pe} | MY{e.get('year') or '?'} | {e['travel']} {e['fit']} | [{e['source']}]")
        print(f"  {e['title']}")
        print(f"  {e['url']}\n")

    with open(out, "w", encoding="utf-8") as f:
        json.dump({"top": fit[:40], "all": results}, f, ensure_ascii=False, indent=2)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
