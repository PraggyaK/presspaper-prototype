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
    key = st.secrets.get("OPENAI_API_KEY")
    if not key:
        st.error("OPENAI_API_KEY missing in Streamlit secrets.")
        st.stop()
    return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ================= HELPERS =================
def clean_text(text: str) -> str:
    junk = [
        "Share this page", "via Facebook", "via X", "via Email",
        "How we use your data", "Cookies", "Accessibility"
    ]
    for j in junk:
        text = text.replace(j, "")
    return re.sub(r"\s+", " ", text).strip()


def generate_summary(text: str) -> str:
    client = get_client()
    text = clean_text(text)

    prompt = f"""
Summarise this Welsh Government document clearly.

Return in this format:

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
        "This document represents an official Welsh Government communication "
        "and affects policy stakeholders, public services, and citizens."
    )


def translate_text(text: str, target_lang: str) -> str:
    client = get_client()

    prompt = f"""
Translate the following government document into {target_lang}.
Keep tone official. Do not add or remove facts.

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
        st.rerun()

# ================= PAGES =================
def page_home():
    st.title("PressPaper")
    st.caption("Verified Welsh Government information — AI summarised")

    def go(cat):
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


def page_browse():
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
            st.rerun()

        if st.button("Clear filters", use_container_width=True):
            st.session_state.filters = {"kw": "", "topics": [], "orgs": []}
            st.rerun()

    with left:
        articles = get_articles(
            category=st.session_state.category,
            kw=st.session_state.filters["kw"],
            topics=st.session_state.filters["topics"],
        )

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

    st.button("← Back to results", on_click=lambda: st.session_state.update(page="browse"))

    st.title(article["title"])
    st.caption(f"{article['published']} · {article['organisations']}")

    st.button("Unsave" if article["saved"] else "Save",
              on_click=toggle_save,
              args=(article["id"],))

    tabs = st.tabs(["Summary", "Context", "Translation", "Original"])

    # -------- SUMMARY --------
    with tabs[0]:
        if st.button("Generate / Refresh summary"):
            s = generate_summary(article["raw_text"])
            update_text(article["id"], "summary", s)
            st.rerun()

        st.markdown(article["summary"] or "_No summary yet_")

        st.subheader("Was this summary helpful?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("👍"):
                st.session_state.summary_feedback[article["id"]] = "helpful"
        with c2:
            if st.button("👎"):
                st.session_state.summary_feedback[article["id"]] = "not helpful"

        st.subheader("Comments & notes")
        note = st.text_area(
            "Your notes",
            value=st.session_state.notes.get(article["id"], "")
        )
        if st.button("Save notes"):
            st.session_state.notes[article["id"]] = note
            st.success("Saved")

    # -------- CONTEXT --------
    with tabs[1]:
        if not article["context"]:
            ctx = generate_context(article)
            update_text(article["id"], "context", ctx)
            st.rerun()
        st.markdown(article["context"])

    # -------- TRANSLATION --------
    with tabs[2]:
        lang = st.selectbox(
            "Target language",
            ["Hindi", "Welsh", "French", "Spanish", "German", "Arabic", "Urdu"],
        )

        if st.button("Translate"):
            with st.spinner("Translating…"):
                tr = translate_text(article["raw_text"], lang)
                update_text(article["id"], "translation", tr)
                st.rerun()

        tr_text = st.text_area(
            f"Translation ({lang})",
            value=article["translation"] or "",
            height=260,
        )

        if st.button("Save translation"):
            update_text(article["id"], "translation", tr_text)
            st.success("Translation saved")

    # -------- ORIGINAL --------
    with tabs[3]:
        st.text_area("Original text", article["raw_text"], height=500)


def page_saved():
    st.title("Saved articles")
    for a in get_saved():
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
