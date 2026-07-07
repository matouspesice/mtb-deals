"""Resolve listing thumbnail URLs from raw scraped data."""
from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

WH_CDN = "https://cache.willhaben.at/mmo/"


def _attr_map(attrs: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for a in (attrs or {}).get("attribute", []):
        vals = a.get("values") or []
        out[a.get("name", "")] = vals[0] if vals else ""
    return out


def willhaben_image(attrs: dict) -> str | None:
    mmo = _attr_map(attrs).get("MMO")
    if mmo:
        return WH_CDN + mmo.lstrip("/")
    all_imgs = _attr_map(attrs).get("ALL_IMAGE_URLS")
    if all_imgs:
        first = all_imgs.split(";")[0].strip()
        if first:
            return WH_CDN + first.lstrip("/")
    return None


def bazos_image(ad_id: str) -> str | None:
    if not ad_id or not str(ad_id).isdigit():
        return None
    sid = str(ad_id)
    return f"https://www.bazos.cz/img/1t/{sid[-3:]}/{sid}.jpg"


def sbazar_image_from_chunk(chunk: str) -> str | None:
    m = re.search(r'"url":\[0,"((?:https?:)?//[^"]+\.(?:jpe?g|webp))"\]', chunk)
    if not m:
        return None
    url = m.group(1)
    if url.startswith("http"):
        return url
    if url.startswith("//"):
        return "https:" + url
    return "https://" + url.lstrip("/")


def buycycle_image_from_blob(blob: str, slug: str) -> str | None:
    i = blob.find(slug)
    if i < 0:
        return None
    window = blob[i : i + 1200]
    m = re.search(
        r'https://d1mgeijqpfaspl\.cloudfront\.net/uploads/bike/media/[^"\\]+\.(?:webp|jpe?g)',
        window,
    )
    if m:
        return m.group(0)
    m = re.search(
        r'https://[^"\\]*cloudfront\.net/uploads/bike/media/[^"\\]+\.(?:webp|jpe?g)',
        window,
    )
    return m.group(0) if m else None


def load_index() -> dict[str, str]:
    """Map listing URL (and id) -> thumbnail image URL."""
    idx: dict[str, str] = {}

    def add(key: str | None, img: str | None) -> None:
        if key and img:
            idx[key] = img

    p = DATA / "at_listings.json"
    if p.exists():
        for item in json.load(open(p, encoding="utf-8")):
            img = willhaben_image(item.get("attributes", {}))
            add(str(item.get("id")), img)
            seo = _attr_map(item.get("attributes", {})).get("SEO_URL", "")
            if seo:
                add(f"https://www.willhaben.at/iad/{seo.rstrip('/')}", img)

    p = DATA / "bazos_listings.json"
    if p.exists():
        for item in json.load(open(p, encoding="utf-8")):
            img = item.get("image_url") or bazos_image(str(item.get("id", "")))
            add(item.get("url"), img)
            add(str(item.get("id")), img)

    p = DATA / "sbazar_listings.json"
    if p.exists():
        for item in json.load(open(p, encoding="utf-8")):
            img = item.get("image_url")
            add(item.get("url"), img)
            add(str(item.get("id")), img)

    p = DATA / "buycycle_listings.json"
    if p.exists():
        for item in json.load(open(p, encoding="utf-8")):
            img = item.get("image_url")
            add(item.get("url"), img)
            add(str(item.get("id")), img)

    p = DATA / "bikefair_listings.json"
    if p.exists():
        for item in json.load(open(p, encoding="utf-8")):
            img = item.get("image_url")
            add(item.get("url"), img)

    for fname in (
        "cyklobazar_listings.json",
        "radbazar_listings.json",
        "radlmarkt_listings.json",
        "biklo_listings.json",
    ):
        p = DATA / fname
        if p.exists():
            for item in json.load(open(p, encoding="utf-8")):
                add(item.get("url"), item.get("image_url"))
                add(str(item.get("id")), item.get("image_url"))

    return idx


def lookup(index: dict[str, str], entry: dict) -> str | None:
    url = entry.get("url") or ""
    if url in index:
        return index[url]
    eid = entry.get("id")
    if eid and str(eid) in index:
        return index[str(eid)]
    m = re.search(r"-(\d{6,})/?", url)
    if m and m.group(1) in index:
        return index[m.group(1)]
    m = re.search(r"/inzerat/(\d+)", url)
    if m and m.group(1) in index:
        return index[m.group(1)]
    return None
