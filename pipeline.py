# pipeline.py
from __future__ import annotations

from database import init_db, insert_article
from extractor_wales import collect_links, extract_article
from topics import guess_topics


def run_pipeline(max_pages_each: int = 2):
    init_db()
    print("🚀 Running pipeline")

    links = collect_links(max_pages_each=max_pages_each)
    print(f"Collected {len(links)} links")

    kept, junked = 0, 0

    for i, item in enumerate(links, 1):
        title = item.get("title") or ""
        url = item.get("url") or ""
        category = item.get("category") or ""

        print(f"[{i}] {category} | {title}")

        text, meta, is_pdf, is_junk, reason = extract_article(url)

        # Only skip if truly junk (explicit junk or empty)
        if is_junk and reason in {"html_empty_or_too_small", "pdf_empty", "pdf_failed"}:
            junked += 1
            print(f"⚠ Skipped ({reason})")
            continue

        text = (text or "").strip()
        if not text:
            junked += 1
            print("⚠ Skipped (no text)")
            continue

        topics = guess_topics(title, text, max_topics=3)
        topics_str = ", ".join(topics) if topics else None

        insert_article(
            category=category,
            title=title,
            url=url,
            published=(meta or {}).get("published"),
            doc_type=(meta or {}).get("doc_type"),
            topics=topics_str,
            organisations=((meta or {}).get("organisations") or "Welsh Government"),
            status=(meta or {}).get("status"),
            image_url=(meta or {}).get("image_url"),
            raw_text=text,
            is_pdf=bool(is_pdf),
        )

        kept += 1

    print(f"✅ Pipeline complete | kept={kept} | junked={junked}")


if __name__ == "__main__":
    run_pipeline(max_pages_each=2)
