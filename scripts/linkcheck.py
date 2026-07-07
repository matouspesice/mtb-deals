"""Verify that listing URLs still point to a live ad and drop dead ones.

Marketplaces (esp. willhaben) return HTTP 200 for expired ads but redirect to a
generic category page, so we inspect the final URL + page title, not just status.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# Titles served when a willhaben ad is gone (redirect to the category page).
CATEGORY_TITLES = (
    "mountainbikes - fahrräder",
    "fahrräder & zubehör",
)
DEAD_MARKERS = (
    "nicht mehr verf", "wurde nicht gefunden", "objekt wurde nicht",
    "anzeige wurde deaktiviert", "existiert nicht", "wurde beendet",
    "inzerát nebyl nalezen", "nabídka byla smazána", "inzerát byl smazán",
    "stránka nenalezena", "404",
)


def _fetch(url: str) -> tuple[int, str, str]:
    req = Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    try:
        with urlopen(req, timeout=15) as r:
            body = r.read(60000).decode("utf-8", "ignore").lower()
            return r.status, r.geturl(), body
    except Exception as e:  # noqa: BLE001
        return int(getattr(e, "code", 0) or -1), url, ""


def _title(body: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", body, re.S)
    return m.group(1).strip() if m else ""


def is_live(url: str) -> bool:
    if not url:
        return False
    code, final, body = _fetch(url)
    if code in (404, 410) or code < 0:
        return False
    title = _title(body)

    if "willhaben.at" in url:
        # Gone ads serve the category page (title "Mountainbikes - Fahrräder ...")
        # at the same URL, so the title is the reliable signal.
        if any(k in title for k in CATEGORY_TITLES):
            return False
        m = re.search(r"-(\d{6,})/?$", url) or re.search(r"/(\d{6,})/?$", url)
        ad_id = m.group(1) if m else None
        if ad_id and ad_id not in final:
            return False
        return True

    if any(k in title for k in DEAD_MARKERS):
        return False
    return True


def filter_live(entries: list[dict], workers: int = 16) -> tuple[list[dict], int]:
    urls = [e.get("url") or "" for e in entries]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        flags = list(ex.map(is_live, urls))
    live = [e for e, ok in zip(entries, flags) if ok]
    return live, len(entries) - len(live)
