from __future__ import annotations
import re
import streamlit as st
from openai import OpenAI

from database import (
    init_db,
    get_articles,
    get_article,
    get_saved,
    toggle_save,
    update_text,
)

# ================= CONFIG =================
st.set_page_config(
    page_title="PressPaper",
    layout="wide",
)

init_db()

# ================= SESSION STATE =================
st.session_state.setdefault("page", "home")
st.session_state.setdefault("category", None)
st.session_state.setdefault("article_id", None)
st.session_state.setdefault("filters", {"kw": "", "topics": [], "orgs": []})
st.session_state.setdefault("notes", {})
st.session_state.setdefault("summary_feedback", {})

# ================= OPENAI =================
def get_client():
    if "OPENAI_API_KEY" not in st.secrets:
        return None
    return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ================= HELPERS =================
def clean_text(text: str) -> str:
    junk = [
        "Share this page", "via Facebook", "via X", "via Email",
        "How we use your data", "Cookies", "Accessibility",
    ]
    for j in junk:
        text = text.replace(j, "")
    return re.sub(r"\s+", " ", text).strip()


def generate_summary(text: str) -> str:
    client = get_client()
    text = clean_text(text)

    if not client:
        return "_AI summary unavailable (missing API key)._"

    prompt = f"""
Summarise this Welsh Government document clearly.

Format:
Key points:
- bullet 1
- bullet 2
- bullet 3

Why it matters:
1–2 sentences.

TEXT:
{text[:6000]}
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You summarise government documents accurately."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return res.choices[0].message.content.strip()


def generate_context(article):
    return (
        f"**Publisher:** {article['organisations']}\n\n"
        f"**Published:** {article['published']}\n\n"
        f"**Topics:** {article['topics']}\n\n"
        "This document represents an official Welsh Government communication."
    )


def translate_text(text: str, target_lang: str) -> str:
    client = get_client()
    if not client:
        return "_Translation unavailable (missing API key)._"

    prompt = f"""
Translate this Welsh Government document into {target_lang}.
Keep tone official and factual.

TEXT:
{text[:6000]}
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You translate government documents faithfully."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
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

    if nav.lower() != st.session_state.page and st.session_state.page != "article":
        st.session_state.page = nav.lower()

# ================= PAGES =================
def page_home():
    st.title("PressPaper")
    st.caption("Welsh Government intelligence — summarised")

    def go(cat):
        st.session_state.category = cat
        st.session_state.page = "browse"

    c1, c2 = st.columns(2)
    with c1:
        st.button("Announcements", on_click=go, args=("Announcements",), use_container_width=True)
        st.button("Publications", on_click=go, args=("Publications",), use_container_width=True)
    with c2:
        st.button("Consultations", on_click=go, args=("Consultations",), use_container_width=True)
        st.button("Statistics & Research", on_click=go, args=("Statistics and Research",), use_container_width=True)


def page_browse():
    if st.button("← Back to Home"):
        st.session_state.page = "home"
        st.session_state.category = None
        return

    st.title(st.session_state.category)

    left, right = st.columns([3, 1], gap="large")

    with right:
        st.subheader("Refine results")

        kw = st.text_input("Keywords", st.session_state.filters["kw"])
        topics = st.multiselect(
            "Topics",
            ["Health", "Education", "Public sector", "Environment", "Transport"],
            st.session_state.filters["topics"],
        )
        orgs = st.multiselect(
            "Organisations",
            ["Welsh Government", "NHS Wales"],
            st.session_state.filters["orgs"],
        )

        if st.button("Apply filters", use_container_width=True):
            st.session_state.filters = {"kw": kw, "topics": topics, "orgs": orgs}

        if st.button("Clear filters", use_container_width=True):
            st.session_state.filters = {"kw": "", "topics": [], "orgs": []}

    with left:
        articles = get_articles(
            category=st.session_state.category,
            kw=st.session_state.filters["kw"],
            topics=st.session_state.filters["topics"],
        )

        if not articles:
            st.info("No articles available yet. Data will appear once ingestion runs.")
            return

        for a in articles:
            if st.session_state.filters["orgs"] and a["organisations"] not in st.session_state.filters["orgs"]:
                continue

            st.markdown(f"### {a['title']}")
            st.caption(f"{a['published']} · {a['organisations']}")
            st.markdown(f"**Topics:** {a['topics']}")

            b1, b2, b3 = st.columns(3)
            with b1:
                st.button("Read", key=f"r{a['id']}", on_click=open_article, args=(a["id"],))
            with b2:
                st.link_button("Source", a["url"])
            with b3:
                st.button("Unsave" if a["saved"] else "Save",
                          key=f"s{a['id']}",
                          on_click=toggle_save,
                          args=(a["id"],))
            st.divider()


def page_article():
    article = get_article(st.session_state.article_id)

    if st.button("← Back to results"):
        st.session_state.page = "browse"
        return

    st.title(article["title"])
    st.caption(f"{article['published']} · {article['organisations']}")

    st.button("Unsave" if article["saved"] else "Save",
              on_click=toggle_save,
              args=(article["id"],))

    tabs = st.tabs(["Summary", "Context", "Translation", "Original"])

    with tabs[0]:
        if st.button("Generate / Refresh summary"):
            s = generate_summary(article["raw_text"])
            update_text(article["id"], "summary", s)

        st.markdown(article["summary"] or "_No summary yet_")

    with tabs[1]:
        if not article["context"]:
            ctx = generate_context(article)
            update_text(article["id"], "context", ctx)
        st.markdown(article["context"])

    with tabs[2]:
        lang = st.selectbox("Target language", ["Hindi", "Welsh", "French", "Spanish"])
        if st.button("Translate"):
            tr = translate_text(article["raw_text"], lang)
            update_text(article["id"], "translation", tr)
        st.text_area("Translation", article["translation"] or "", height=260)

    with tabs[3]:
        st.text_area("Original text", article["raw_text"], height=500)


def page_saved():
    st.title("Saved articles")
    saved = get_saved()
    if not saved:
        st.info("No saved articles yet.")
        return

    for a in saved:
        st.markdown(f"### {a['title']}")
        st.button("Read", key=f"sr{a['id']}", on_click=open_article, args=(a["id"],))
        st.button("Unsave", key=f"us{a['id']}", on_click=toggle_save, args=(a["id"],))
        st.divider()

# ================= ROUTER =================
if st.session_state.page == "home":
    page_home()
elif st.session_state.page == "browse":
    page_browse()
elif st.session_state.page == "article":
    page_article()
elif st.session_state.page == "saved":
    page_saved()