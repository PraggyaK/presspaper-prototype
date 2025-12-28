# ingest_service/main.py
from __future__ import annotations

import os
import time
import threading
from fastapi import FastAPI
from database import init_db, upsert_article
from ingest_service.scraper import collect_links, extract_article

app = FastAPI()

def run_ingest_once(max_pages_each: int = 2) -> dict:
    init_db()

    links = collect_links(max_pages_each=max_pages_each)
    kept = 0
    skipped = 0

    for item in links:
        url = item["url"]
        title = item["title"]
        category = item["category"]

        text, meta, is_pdf, is_junk, reason = extract_article(url)

        if is_junk:
            skipped += 1
            continue

        a = {
            "category": category,
            "title": title,
            "url": url,
            "published": (meta or {}).get("published"),
            "doc_type": (meta or {}).get("doc_type"),
            "topics": (meta or {}).get("topics"),
            "organisations": (meta or {}).get("organisations") or "Welsh Government",
            "status": (meta or {}).get("status"),
            "image_url": (meta or {}).get("image_url"),
            "raw_text": text,
            "is_pdf": bool(is_pdf),
        }
        upsert_article(a)
        kept += 1

    return {"kept": kept, "skipped": skipped, "total_links": len(links)}

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/run")
def run_now():
    return run_ingest_once(max_pages_each=2)

def background_scheduler():
    minutes = int(os.getenv("INGEST_INTERVAL_MINUTES", "15"))
    while True:
        try:
            run_ingest_once(max_pages_each=2)
        except Exception as e:
            # do not crash service
            print("INGEST ERROR:", e)
        time.sleep(minutes * 60)

@app.on_event("startup")
def start_scheduler():
    # start background loop on the ingestion server (NOT Streamlit Cloud)
    t = threading.Thread(target=background_scheduler, daemon=True)
    t.start()
