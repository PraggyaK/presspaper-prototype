# extractor_wales.py
from __future__ import annotations

from playwright.sync_api import sync_playwright
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

JUNK_TITLE_PATTERNS = [
    r"^home$",
    r"^rss$",
    r"^newsletter.*",
    r"sign up",
    r"subscribe",
    r"clear filters",
    r"skip to",
    r"previous page",
    r"next page",
    r"^page\s*\d+$",
    r"^\d+$",
    r"report anything wrong",
    r"share this page",
    r"about consultations",
    r"about statistics and research",
    r"how we use your data",
    r"terms and conditions",
    r"accessibility",
]

JUNK_URL_BITS = [
    "/rss",
    "/cookies",
    "/privacy",
    "/terms",
    "/accessibility",
    "/sitemap",
    "/search",
    "/newsletter",
]


def looks_like_junk(title: str, url: str):
    t = (title or "").strip().lower()
    u = (url or "").strip().lower()

    for bit in JUNK_URL_BITS:
        if bit in u:
            return True, f"url:{bit}"

    for pat in JUNK_TITLE_PATTERNS:
        if re.search(pat, t):
            return True, f"title:{pat}"

    if t.startswith("view all"):
        return True, "view_all"

    return False, None


def collect_links(max_pages_each: int = 2):
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for category, path in CATEGORIES.items():
            for i in range(max_pages_each):
                url = f"{BASE}{path}?page={i}"
                print(f"Fetching: {url}")

                page.goto(url, timeout=60000)
                page.wait_for_load_state("networkidle")

                anchors = page.query_selector_all("main a[href]")

                for a in anchors:
                    href = a.get_attribute("href") or ""
                    title = (a.inner_text() or "").strip()

                    if not href.startswith("/"):
                        continue
                    if len(title) < 8:
                        continue

                    full_url = urljoin(BASE, href)

                    is_junk, _ = looks_like_junk(title, full_url)
                    if is_junk:
                        continue

                    results.append(
                        {"category": category, "title": title, "url": full_url}
                    )

        browser.close()

    unique = {r["url"]: r for r in results}
    print(f"Collected {len(unique)} real articles")
    return list(unique.values())


def _clean_text(s: str) -> str:
    return " ".join((s or "").replace("\xa0", " ").split()).strip()


def extract_metadata_and_text(url: str):
    """
    Returns: (text, meta, is_pdf, is_junk, junk_reason)
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=35)
    except Exception as e:
        return "", {}, False, True, f"request_failed:{e}"

    ct = (r.headers.get("content-type") or "").lower()

    # PDF
    if "pdf" in ct or url.lower().endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(r.content))
            text = "\n".join(_clean_text(p.extract_text() or "") for p in reader.pages)
            text = _clean_text(text)
            if not text:
                return "", {}, True, True, "pdf_empty"
            return text, {}, True, False, None
        except Exception:
            return "", {}, True, True, "pdf_failed"

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

    time_tag = soup.find("time")
    if time_tag and time_tag.get("datetime"):
        meta["published"] = time_tag["datetime"].strip()

    # Extract broadly. GOV pages are inconsistent.
    selectors = [
        "h1", "h2", "h3",
        "p", "li",
        "div.field__item", "div.field",
        "div.content", "section",
    ]

    parts = []
    for el in main.select(",".join(selectors)):
        txt = _clean_text(el.get_text(" ", strip=True))
        # keep smaller fragments too; many real pages are short
        if txt and len(txt) >= 20:
            parts.append(txt)

    text = "\n\n".join(parts).strip()

    # Hard junk detection: truly empty
    if len(text) < 80:  # characters, not words
        # still keep if it at least has a title-ish h1
        h1 = main.find("h1")
        if h1 and _clean_text(h1.get_text()) and len(_clean_text(h1.get_text())) >= 8:
            # keep minimal pages
            return text, meta, False, False, None
        return text, meta, False, True, "html_empty_or_too_small"

    return text, meta, False, False, None


def extract_article(url: str):
    return extract_metadata_and_text(url)
