# extractor_wales.py
from __future__ import annotations

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from PyPDF2 import PdfReader
import io
import re

BASE = "https://www.gov.wales"

CATEGORIES = {
    "Announcements": "/announcements",
    "Consultations": "/consultations",
    "Publications": "/publications",
    "Statistics and Research": "/statistics-and-research",
}

HEADERS = {"User-Agent": "PressPaper/1.0"}

JUNK_URL_BITS = [
    "/rss", "/cookies", "/privacy", "/terms",
    "/accessibility", "/sitemap", "/search",
]

def looks_like_junk(title: str, url: str) -> bool:
    t = (title or "").lower()
    u = (url or "").lower()

    if len(t) < 8:
        return True

    for bit in JUNK_URL_BITS:
        if bit in u:
            return True

    return False


def collect_links(max_pages_each: int = 2):
    results = []

    for category, path in CATEGORIES.items():
        for page_no in range(max_pages_each):
            url = f"{BASE}{path}?page={page_no}"
            print(f"Fetching: {url}")

            r = requests.get(url, headers=HEADERS, timeout=30)
            soup = BeautifulSoup(r.text, "html.parser")

            for a in soup.select("main a[href]"):
                href = a.get("href")
                title = a.get_text(strip=True)

                if not href or not href.startswith("/"):
                    continue

                full_url = urljoin(BASE, href)

                if looks_like_junk(title, full_url):
                    continue

                results.append({
                    "category": category,
                    "title": title,
                    "url": full_url,
                })

    unique = {r["url"]: r for r in results}
    print(f"Collected {len(unique)} articles")
    return list(unique.values())


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def extract_article(url: str):
    r = requests.get(url, headers=HEADERS, timeout=30)
    ct = (r.headers.get("content-type") or "").lower()

    # -------- PDF --------
    if "pdf" in ct or url.lower().endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(r.content))
            text = "\n".join(_clean_text(p.extract_text()) for p in reader.pages if p.extract_text())
            return text, {"organisations": "Welsh Government"}, False
        except Exception:
            return "", {}, True

    # -------- HTML --------
    soup = BeautifulSoup(r.text, "html.parser")
    main = soup.find("main") or soup

    for tag in main.select("script, style, nav, footer, header, aside"):
        tag.decompose()

    parts = []
    for p in main.find_all(["p", "li", "h2", "h3"]):
        txt = _clean_text(p.get_text())
        if len(txt) > 30:
            parts.append(txt)

    text = "\n\n".join(parts)

    meta = {
        "organisations": "Welsh Government",
        "published": None,
        "topics": None,
    }

    time_tag = soup.find("time")
    if time_tag and time_tag.get("datetime"):
        meta["published"] = time_tag["datetime"]

    return text, meta, False
