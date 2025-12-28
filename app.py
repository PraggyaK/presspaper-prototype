# app.py
from __future__ import annotations

import os
import re
import streamlit as st
from openai import OpenAI
from database import (
    init_db, get_articles, get_article, toggle_save, update_text, get_distinct_values
)

# ================= CONFIG =================
st.set_page_config(page_title="PressPaper", layout="wide")
init_db()

# ================= STATE =================
st.session_state.setdefault("page", "home")
st.session_state.setdefault("category", None)
st.session_state.setdefault("article_id", None)
st.session_state.setdefault("filters", {"kw": "", "topics": [], "orgs": []})

# ================= OPENAI =================
def get_client() -> OpenAI | None:
    key = None
    try:
        key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        pass
    if not key:
        key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    return OpenAI(api_key=key)

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    return text

def generate_summary(text: str) -> str:
    client = get_client()
    text = clean_text(text)
    if not client:
        return "_AI summary unavailable (missing OPENAI_API_KEY in secrets)._"

    prompt = f"""
You summarise Welsh Government documents.

Return EXACTLY this markdown:

### Key points
- ...
- ...
- ...
- ...
- ...

### What changed / what’s new
1–2 bullets.

### Why it matters
2–3 sentences, practical.

### Who is affected
A short list.

Document text:
{text[:9000]}
"""
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {"role": "system", "content": "Be accurate, non-hallucinating, concise. If unknown, say 'Not stated'."},
            {"role": "user", "content": prompt},
        ],
    )
    return res.choices[0].message.content.strip()

def generate_context(article: dict) -> str:
    # cheap but reliable (no hallucination)
    return (
        f"### Document context\n"
        f"**Publisher:** {article.get('organisations') or 'Not stated'}  \n"
        f"**Published:** {article.get('published') or 'Not stated'}  \n"
        f"**Category:** {article.get('category') or 'Not stated'}  \n"
        f"**Topics:** {article.get('topics') or 'Not stated'}  \n\n"
        f"This is an official Welsh Government page. The sections below (summary/translation) are generated from the document text."
    )

def translate_text(text: str, target_lang: str) -> str:
    client = get_client()
    text = clean_text(text)
    if not client:
        return "_Translation unavailable (missing OPENAI_API_KEY in secrets)._"

    prompt = f"""
Translate the following government document into {target_lang}.
Rules:
- Keep meaning faithful; do not add facts.
- Keep official tone.
- Preserve lists and headings.

TEXT:
{text[:9000]}
"""
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {"role": "system", "content": "Translate faithfully and professionally."},
            {"role": "user", "content": prompt},
        ],
    )
    return res.choices[0].message.content.strip()

def open_article(article_id: int):
    st.session_state.article_id = article_id
    st.session_state.page = "article"

# ================= SIDEBAR =================
with st.sidebar:
    st.title("📰 PressPaper")

    nav = st.radio(
        "Navigation",
        ["Home", "Browse", "Saved"],
        index=["home", "browse", "saved"].index(
            "browse" if st.session_state.page == "article" else st.session_state.page
        ),
    )

    # NOTE: Do NOT set nav after widget; only set page
    if nav.lower() != st.session_state.page and st.session_state.page != "article":
        st.session_state.page = nav.lower()
        st.rerun()

# ================= UI polish (safe CSS) =================
st.markdown("""
<style>
.block-container { padding-top: 1.2rem; }
h1, h2, h3 { letter-spacing: -0.02em; }
.small-muted { color: rgba(0,0,0,.55); font-size: 0.9rem; }
.card { padding: 1rem; border: 1px solid rgba(49,51,63,.15); border-radius: 14px; }
</style>
""", unsafe_allow_html=True)

# ================= PAGES =================
def page_home():
    st.title("PressPaper")
    st.caption("Welsh Government intelligence — live ingestion + AI summary + translation")

    st.subheader("Choose a section")
    def go(cat: str):
        st.session_state.category = cat
        st.session_state.page = "browse"
        st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        st.button("Announcements", on_click=go, args=("Announcements",), use_container_width=True)
        st.button("Publications", on_click=go, args=("Publications",), use_container_width=True)
    with c2:
        st.button("Consultations", on_click=go, args=("Consultations",), use_container_width=True)
        st.button("Statistics and Research", on_click=go, args=("Statistics and Research",), use_container_width=True)

    st.markdown('<div class="small-muted">If Browse shows no articles, your ingestion service hasn’t populated the database yet.</div>', unsafe_allow_html=True)

def page_browse(saved_only: bool = False):
    top = st.container()
    with top:
        c1, c2 = st.columns([1, 4])
        with c1:
            st.button("← Back", on_click=lambda: (st.session_state.update(page="home", category=None), st.rerun()), use_container_width=True)
        with c2:
            title = "Saved articles" if saved_only else (st.session_state.category or "Browse")
            st.title(title)

    left, right = st.columns([3, 1], gap="large")

    with right:
        st.subheader("Refine results")
        kw = st.text_input("Keywords", st.session_state.filters["kw"])

        # dynamic options from DB (best UX)
        topic_options = get_distinct_values("topics") or ["Health", "Education", "Public sector", "Environment", "Transport"]
        org_options = get_distinct_values("organisations") or ["Welsh Government"]

        topics = st.multiselect("Topics", topic_options, default=st.session_state.filters["topics"])
        orgs = st.multiselect("Organisations", org_options, default=st.session_state.filters["orgs"])

        a1, a2 = st.columns(2)
        with a1:
            if st.button("Apply", use_container_width=True):
                st.session_state.filters = {"kw": kw, "topics": topics, "orgs": orgs}
                st.rerun()
        with a2:
            if st.button("Reset", use_container_width=True):
                st.session_state.filters = {"kw": "", "topics": [], "orgs": []}
                st.rerun()

        st.divider()
        st.markdown("**Tip:** Use Saved to build your own reading list.")

    with left:
        articles = get_articles(
            category=None if saved_only else st.session_state.category,
            kw=st.session_state.filters["kw"],
            topics=st.session_state.filters["topics"],
            orgs=st.session_state.filters["orgs"],
            saved_only=saved_only,
            limit=200,
        )

        if not articles:
            st.warning("No articles found yet. This usually means the ingestion service hasn’t written into the DB.")
            return

        for a in articles:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f"### {a['title']}")
            st.caption(f"{a.get('published') or '—'} · {a.get('organisations') or '—'}")
            st.markdown(f"**Topics:** {a.get('topics') or '—'}")

            b1, b2, b3 = st.columns([1, 1, 1])
            with b1:
                st.button("Read", key=f"read_{a['id']}", on_click=open_article, args=(a["id"],), use_container_width=True)
            with b2:
                st.link_button("Source", a["url"], use_container_width=True)
            with b3:
                st.button("Unsave" if a["saved"] else "Save", key=f"save_{a['id']}",
                          on_click=toggle_save, args=(a["id"],), use_container_width=True)

            st.markdown("</div>", unsafe_allow_html=True)
            st.write("")

def page_article():
    article = get_article(int(st.session_state.article_id))
    if not article:
        st.session_state.page = "browse"
        st.rerun()

    c1, c2, c3 = st.columns([1, 3, 1])
    with c1:
        st.button("← Back", on_click=lambda: (st.session_state.update(page="browse"), st.rerun()), use_container_width=True)
    with c3:
        st.button("Unsave" if article["saved"] else "Save",
                  on_click=toggle_save, args=(article["id"],), use_container_width=True)

    st.title(article["title"])
    st.caption(f"{article.get('published') or '—'} · {article.get('organisations') or '—'}")

    tabs = st.tabs(["Summary", "Context", "Translation", "Original"])

    # -------- SUMMARY --------
    with tabs[0]:
        cA, cB = st.columns([1, 2])
        with cA:
            if st.button("Generate / Refresh summary", use_container_width=True):
                with st.spinner("Generating summary…"):
                    s = generate_summary(article["raw_text"] or "")
                    update_text(article["id"], "summary", s)
                st.rerun()

        st.markdown(article.get("summary") or "_No summary yet. Click 'Generate / Refresh summary'._")

        st.divider()
        st.subheader("Summary feedback")
        fb = article.get("summary_feedback") or ""
        f1, f2, f3 = st.columns(3)
        with f1:
            if st.button("👍 Helpful", use_container_width=True):
                update_text(article["id"], "summary_feedback", "helpful")
                st.rerun()
        with f2:
            if st.button("👎 Not helpful", use_container_width=True):
                update_text(article["id"], "summary_feedback", "not_helpful")
                st.rerun()
        with f3:
            if st.button("⚠ Needs rewrite", use_container_width=True):
                update_text(article["id"], "summary_feedback", "needs_rewrite")
                st.rerun()

        st.markdown(f"<div class='small-muted'>Current: <b>{fb or '—'}</b></div>", unsafe_allow_html=True)

        st.divider()
        st.subheader("Comments & notes")
        notes_val = article.get("notes") or ""
        notes = st.text_area("Your notes (saved to database)", value=notes_val, height=140)
        if st.button("Save notes"):
            update_text(article["id"], "notes", notes)
            st.success("Saved")
            st.rerun()

    # -------- CONTEXT --------
    with tabs[1]:
        if not article.get("context"):
            ctx = generate_context(article)
            update_text(article["id"], "context", ctx)
            article = get_article(int(st.session_state.article_id))  # refresh
        st.markdown(article.get("context") or "")

    # -------- TRANSLATION --------
    with tabs[2]:
        lang = st.selectbox(
            "Translate to",
            ["Hindi", "Welsh", "French", "Spanish", "German", "Arabic", "Urdu", "Punjabi", "Italian", "Portuguese"],
        )

        cT1, cT2 = st.columns([1, 2])
        with cT1:
            if st.button("Translate", use_container_width=True):
                with st.spinner("Translating…"):
                    tr = translate_text(article["raw_text"] or "", lang)
                    update_text(article["id"], "translation", tr, translation_lang=lang)
                st.rerun()
        with cT2:
            st.markdown(f"<div class='small-muted'>Stored translation language: <b>{article.get('translation_lang') or '—'}</b></div>", unsafe_allow_html=True)

        tr_val = article.get("translation") or ""
        tr_edit = st.text_area("Translation (editable)", value=tr_val, height=260)

        if st.button("Save translation edits"):
            update_text(article["id"], "translation", tr_edit, translation_lang=lang)
            st.success("Saved")
            st.rerun()

    # -------- ORIGINAL --------
    with tabs[3]:
        st.text_area("Original text", value=article.get("raw_text") or "", height=520)

def page_saved():
    page_browse(saved_only=True)

# ================= ROUTER =================
if st.session_state.page == "home":
    page_home()
elif st.session_state.page == "browse":
    page_browse(saved_only=False)
elif st.session_state.page == "article":
    page_article()
elif st.session_state.page == "saved":
    page_saved()
else:
    st.session_state.page = "home"
    st.rerun()
