import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://www.gov.wales"
HEADERS = {"User-Agent": "PressPaper Prototype"}
TIMEOUT = 25

CATEGORIES = {
    "Announcements": "announcements",
    "Consultations": "consultations",
    "Publications": "publications",
    "Statistics and Research": "statistics-and-research",
}


def _clean(s: str) -> str:
    return " ".join((s or "").split()).strip()


def _collect_from_listing(category_name: str, slug: str, max_pages: int):
    """
    Collect links from listing pages like:
      https://www.gov.wales/announcements?page=0
    Gov.wales markup changes sometimes; keep selectors flexible.
    """
    out = []
    for p in range(max_pages):
        url = f"{BASE}/{slug}?page={p}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
        except Exception:
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        # Most listings contain <a> cards. We'll pull main results links.
        # Heuristic: links inside main content that look like content pages.
        main = soup.find("main") or soup.body
        if not main:
            continue

        anchors = main.select("a[href]")
        for a in anchors:
            href = a.get("href") or ""
            text = _clean(a.get_text(" ", strip=True))
            if not href or not text:
                continue

            full = urljoin(BASE, href)

            # exclude obvious navigation links
            if full.endswith(slug) or full.endswith(slug + "/"):
                continue
            if "/node/" in full:
                continue

            # avoid duplicates
            out.append({
                "category": category_name,
                "title": text,
                "url": full,
            })

    # de-dup by url preserving order
    seen = set()
    dedup = []
    for item in out:
        if item["url"] not in seen:
            seen.add(item["url"])
            dedup.append(item)
    return dedup


def fetch_wales_links(max_pages_each: int = 2):
    all_items = []
    for cat, slug in CATEGORIES.items():
        all_items.extend(_collect_from_listing(cat, slug, max_pages_each))
    return all_items