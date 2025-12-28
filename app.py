from __future__ import annotations
import re
import streamlit as st
from googletrans import Translator

from database import (
    init_db,
    get_articles,
    get_article,
    get_saved,
    toggle_save,
    update_text,
)

# ================= CONFIG =================
st.set_page_config("PressPaper", layout="wide")
init_db()
translator = Translator()

# ================= SESSION STATE =================
st.session_state.setdefault("page", "home")
st.session_state.setdefault("category", None)
st.session_state.setdefault("article_id", None)
st.session_state.setdefault("filters", {"kw": "", "topics": [], "orgs": []})
st.session_state.setdefault("notes", {})
st.session_state.setdefault("summary_feedback", {})

# ================= HELPERS =================
def clean_text(text: str) -> str:
    junk = [
        "Share this page", "via Facebook", "via X", "via Email",
        "Cookies", "Accessibility", "How we use your data"
    ]
    for j in junk:
        text = text.replace(j, "")
    return re.sub(r"\s+", " ", text).strip()


def generate_summary(text: str) -> str:
    text = clean_text(text)
    sentences = [s.strip() for s in text.split(". ") if len(s) > 40]

    if not sentences:
        return "_Not enough content to summarise._"

    overview = sentences[0]
    bullets = sentences[1:5]
    impact = sentences[-1]

    return (
        "### Overview\n"
        f"{overview}.\n\n"
        "### Key points\n" +
        "\n".join(f"- {b}." for b in bullets) +
        "\n\n### Why it matters\n"
        f"{impact}."
    )


def generate_context(article) -> str:
    return (
        f"This document was published by **{article['organisations']}** "
        f"on **{article['published']}**.\n\n"
        f"It relates to **{article['topics']}** and communicates official "
        "government policy, announcements, or data.\n\n"
        "It is relevant to public bodies, policymakers, service providers, "
        "and the general public."
    )


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
    st.caption("Verified Welsh Government information — AI summarised")

    def go(cat):
        st.session_state.category = cat
        st.session_state.page = "browse"

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

        # get all orgs from DB results
        all_articles = get_articles(st.session_state.category, "", [])
        all_orgs = sorted({a["organisations"] for a in all_articles if a["organisations"]})

        orgs = st.multiselect(
            "Organisations",
            all_orgs,
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

        # apply organisation filter safely in Python
        if st.session_state.filters["orgs"]:
            articles = [
                a for a in articles
                if a["organisations"] in st.session_state.filters["orgs"]
            ]

        if not articles:
            st.info("No articles match your filters.")
            return

        for a in articles:
            st.markdown(f"### {a['title']}")
            st.caption(f"{a['published']} · {a['organisations']}")
            st.markdown(f"**Topics:** {a['topics']}")

            c1, c2, c3 = st.columns(3)
            with c1:
                st.button("Read", key=f"r{a['id']}", on_click=open_article, args=(a["id"],))
            with c2:
                st.link_button("Source", a["url"])
            with c3:
                st.button(
                    "Unsave" if a["saved"] else "Save",
                    key=f"s{a['id']}",
                    on_click=toggle_save,
                    args=(a["id"],),
                )
            st.divider()


def page_article():
    article = get_article(st.session_state.article_id)

    st.button("← Back to results", on_click=lambda: st.session_state.update(page="browse"))

    st.title(article["title"])
    st.caption(f"{article['published']} · {article['organisations']}")

    st.button(
        "Unsave" if article["saved"] else "Save",
        on_click=toggle_save,
        args=(article["id"],),
    )

    tabs = st.tabs(["Summary", "Context", "Translation", "Original"])

    with tabs[0]:
        if st.button("Generate / Refresh summary"):
            summary = generate_summary(article["raw_text"])
            update_text(article["id"], "summary", summary)

        st.markdown(article["summary"] or "_No summary yet_")

        st.markdown("**Was this summary helpful?**")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("👍"):
                st.session_state.summary_feedback[article["id"]] = "positive"
        with c2:
            if st.button("👎"):
                st.session_state.summary_feedback[article["id"]] = "negative"

        st.subheader("Comments & notes")
        note = st.text_area(
            "Your notes",
            value=st.session_state.notes.get(article["id"], ""),
            height=120,
        )
        if st.button("Save notes"):
            st.session_state.notes[article["id"]] = note
            st.success("Saved")

    with tabs[1]:
        if not article.get("context"):
            ctx = generate_context(article)
            update_text(article["id"], "context", ctx)
        st.markdown(article["context"])

    with tabs[2]:
        languages = {
            "English": "en",
            "Welsh": "cy",
            "Hindi": "hi",
            "French": "fr",
            "Spanish": "es",
            "German": "de",
            "Italian": "it",
            "Portuguese": "pt",
            "Arabic": "ar",
            "Chinese": "zh-cn",
        }

        lang = st.selectbox("Translate to", list(languages.keys()))
        if st.button("Translate"):
            translated = translator.translate(
                article["raw_text"], dest=languages[lang]
            ).text
            update_text(article["id"], "translation", translated)

        tr = st.text_area(
            "Translated text",
            value=article.get("translation") or "",
            height=300,
        )

        if st.button("Save translation"):
            update_text(article["id"], "translation", tr)
            st.success("Translation saved")

    with tabs[3]:
        st.text_area("Original document", article["raw_text"], height=500)


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
