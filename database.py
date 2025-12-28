# database.py
import sqlite3
from pathlib import Path

DB_PATH = Path("presspaper.db")


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            title TEXT,
            url TEXT UNIQUE,
            published TEXT,
            doc_type TEXT,
            topics TEXT,
            organisations TEXT,
            status TEXT,
            image_url TEXT,
            raw_text TEXT,
            summary TEXT,
            context TEXT,
            translation TEXT,
            is_pdf INTEGER DEFAULT 0,
            saved INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def insert_article(**kwargs):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO articles (
            category, title, url, published,
            doc_type, topics, organisations,
            status, image_url, raw_text, is_pdf
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        kwargs["category"],
        kwargs["title"],
        kwargs["url"],
        kwargs["published"],
        kwargs["doc_type"],
        kwargs["topics"],
        kwargs["organisations"],
        kwargs["status"],
        kwargs["image_url"],
        kwargs["raw_text"],
        int(kwargs["is_pdf"]),
    ))

    conn.commit()
    conn.close()


def get_articles(category=None, kw=None, topics=None):
    conn = get_conn()
    cur = conn.cursor()

    q = "SELECT * FROM articles WHERE 1=1"
    p = []

    if category:
        q += " AND category = ?"
        p.append(category)

    if kw:
        q += " AND title LIKE ?"
        p.append(f"%{kw}%")

    if topics:
        for t in topics:
            q += " AND topics LIKE ?"
            p.append(f"%{t}%")

    q += " ORDER BY published DESC"
    cur.execute(q, p)

    rows = cur.fetchall()
    conn.close()
    return [_row(r) for r in rows]


def get_article(article_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
    row = cur.fetchone()
    conn.close()
    return _row(row) if row else None


def get_saved():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM articles WHERE saved = 1 ORDER BY published DESC")
    rows = cur.fetchall()
    conn.close()
    return [_row(r) for r in rows]


def toggle_save(article_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE articles SET saved = 1 - saved WHERE id = ?", (article_id,))
    conn.commit()
    conn.close()


def update_text(article_id, field, value):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE articles SET {field} = ? WHERE id = ?", (value, article_id))
    conn.commit()
    conn.close()


def _row(r):
    keys = [
        "id", "category", "title", "url", "published",
        "doc_type", "topics", "organisations", "status",
        "image_url", "raw_text", "summary", "context",
        "translation", "is_pdf", "saved"
    ]
    return dict(zip(keys, r))
