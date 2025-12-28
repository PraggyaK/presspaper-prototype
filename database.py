# database.py
from __future__ import annotations

import os
import psycopg
from psycopg.rows import dict_row

def get_db_url() -> str:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")
    return db_url

def get_conn():
    return psycopg.connect(get_db_url(), row_factory=dict_row)

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Core table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id BIGSERIAL PRIMARY KEY,
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
                is_pdf BOOLEAN DEFAULT FALSE,

                summary TEXT,
                context TEXT,
                translation TEXT,
                translation_lang TEXT,

                saved BOOLEAN DEFAULT FALSE,
                notes TEXT,
                summary_feedback TEXT,

                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """)

            # lightweight trigger to keep updated_at fresh
            cur.execute("""
            CREATE OR REPLACE FUNCTION set_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
              NEW.updated_at = NOW();
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """)

            cur.execute("""
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_trigger WHERE tgname = 'trg_articles_updated_at'
              ) THEN
                CREATE TRIGGER trg_articles_updated_at
                BEFORE UPDATE ON articles
                FOR EACH ROW EXECUTE FUNCTION set_updated_at();
              END IF;
            END$$;
            """)

        conn.commit()

def upsert_article(a: dict):
    """
    a must include: category,title,url,published,doc_type,topics,organisations,status,image_url,raw_text,is_pdf
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO articles (
              category, title, url, published, doc_type, topics, organisations, status,
              image_url, raw_text, is_pdf
            )
            VALUES (
              %(category)s, %(title)s, %(url)s, %(published)s, %(doc_type)s, %(topics)s, %(organisations)s, %(status)s,
              %(image_url)s, %(raw_text)s, %(is_pdf)s
            )
            ON CONFLICT (url) DO UPDATE SET
              category = EXCLUDED.category,
              title = EXCLUDED.title,
              published = EXCLUDED.published,
              doc_type = EXCLUDED.doc_type,
              topics = EXCLUDED.topics,
              organisations = EXCLUDED.organisations,
              status = EXCLUDED.status,
              image_url = EXCLUDED.image_url,
              raw_text = EXCLUDED.raw_text,
              is_pdf = EXCLUDED.is_pdf
            """, a)
        conn.commit()

def get_articles(category: str | None = None, kw: str | None = None, topics: list[str] | None = None,
                 orgs: list[str] | None = None, saved_only: bool = False, limit: int = 200):
    topics = topics or []
    orgs = orgs or []

    query = "SELECT * FROM articles WHERE 1=1"
    params = {}

    if category:
        query += " AND category = %(category)s"
        params["category"] = category

    if saved_only:
        query += " AND saved = TRUE"

    if kw:
        query += " AND title ILIKE %(kw)s"
        params["kw"] = f"%{kw}%"

    # topics stored as comma string, so use ILIKE checks
    for i, t in enumerate(topics):
        query += f" AND COALESCE(topics,'') ILIKE %(t{i})s"
        params[f"t{i}"] = f"%{t}%"

    for i, o in enumerate(orgs):
        query += f" AND COALESCE(organisations,'') ILIKE %(o{i})s"
        params[f"o{i}"] = f"%{o}%"

    query += " ORDER BY published DESC NULLS LAST, updated_at DESC LIMIT %(limit)s"
    params["limit"] = limit

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

def get_article(article_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM articles WHERE id = %s", (article_id,))
            return cur.fetchone()

def toggle_save(article_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE articles SET saved = NOT saved WHERE id = %s RETURNING saved", (article_id,))
            new_val = cur.fetchone()["saved"]
        conn.commit()
    return new_val

def update_text(article_id: int, field: str, value: str, translation_lang: str | None = None):
    allowed = {"summary", "context", "translation", "notes", "summary_feedback"}
    if field not in allowed:
        raise ValueError("Invalid field")

    with get_conn() as conn:
        with conn.cursor() as cur:
            if field == "translation":
                cur.execute(
                    "UPDATE articles SET translation=%s, translation_lang=%s WHERE id=%s",
                    (value, translation_lang, article_id),
                )
            else:
                cur.execute(f"UPDATE articles SET {field}=%s WHERE id=%s", (value, article_id))
        conn.commit()

def get_distinct_values(col: str, limit: int = 50):
    if col not in {"topics", "organisations"}:
        raise ValueError("Invalid column")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT DISTINCT {col} FROM articles WHERE {col} IS NOT NULL LIMIT %s", (limit,))
            rows = cur.fetchall()
    # flatten & split comma strings
    vals = []
    for r in rows:
        raw = r[col]
        if not raw:
            continue
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        vals.extend(parts)
    # unique preserve order
    seen = set()
    out = []
    for v in vals:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out[:limit]
