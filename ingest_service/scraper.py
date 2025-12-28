# ingest_service/scraper.py
from __future__ import annotations

import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://www.gov.wales"

CATEGORIES = {
    "Announcements": "/announcements",
    "Consultations": "/consultations",
    "Publications": "/publications",
    "Statistics and Research": "/statistics-and-research",
}

HEADERS = {"User-Agent": "PressPaper/1.0 (+contact: presspaper)"}

JUNK_URL_BITS = ["/rss", "/cookies", "/privacy", "/terms", "/accessibility", "/sitemap", "/search", "/newsletter"]

def _clean_text(s: str) -> str:
    return " ".join((s or "").replace("\xa0", " ").split()).strip()

def looks_junk(url: str) -> bool:
    u = (url or "").lower()
    return any(bit in u for bit in JUNK_URL_BITS)

def collect_links(max_pages_each: int = 2) -> list[dict]:
    out = []
    for category, path in CATEGORIES.items():
        for page in range(max_pages_each):
            url = f"{BASE}{path}?page={page}"
            r = requests.get(url, headers=HEADERS, timeout=35)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            main = soup.find("main") or soup
            for a in main.select("a[href]"):
                href = a.get("href") or ""
                title = _clean_text(a.get_text(" ", strip=True))
                if not href.startswith("/"):
                    continue
                if len(title) < 12:
                    continue

                full = urljoin(BASE, href)
                if looks_junk(full):
                    continue

                # heuristic: only keep actual nodes (most gov pages include /news/ or similar,
                # but we keep it open and rely on extraction size)
                out.append({"category": category, "title": title, "url": full})

            time.sleep(0.2)

    # unique by URL
    uniq = {}
    for item in out:
        uniq[item["url"]] = item
    return list(uniq.values())

def extract_article(url: str) -> tuple[str, dict, bool, bool, str | None]:
    """
    Returns (text, meta, is_pdf, is_junk, reason)
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=35)
    except Exception as e:
        return "", {}, False, True, f"request_failed:{e}"

    ct = (r.headers.get("content-type") or "").lower()
    if "pdf" in ct or url.lower().endswith(".pdf"):
        # skip pdf for now (can add later)
        return "", {}, True, True, "pdf_skipped"

    soup = BeautifulSoup(r.text, "html.parser")
    main = soup.find("main") or soup

    for tag in main.select("script, style, nav, footer, header, form, aside"):
        tag.decompose()

    meta = {
        "published": None,
        "doc_type": None,
        "status": None,
        "topics": None,
        "organisations": "Welsh Government",
        "image_url": None,
    }

    t = soup.find("time")
    if t and t.get("datetime"):
        meta["published"] = t["datetime"].strip()

    parts = []
    for el in main.select("h1, h2, h3, p, li"):
        txt = _clean_text(el.get_text(" ", strip=True))
        if txt and len(txt) >= 25:
            parts.append(txt)

    text = "\n\n".join(parts).strip()

    # junk if too small
    if len(text) < 250:
        return text, meta, False, True, "too_small"

    return text, meta, False, False, None
