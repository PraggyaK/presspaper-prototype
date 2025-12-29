from __future__ import annotations

import re
import requests
import streamlit as st
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from openai import OpenAI

# ================== CONFIG ==================
st.set_page_config(page_title="PressPaper", layout="wide")

BASE = "https://www.gov.wales"

CATEGORIES = {
    "Announcements": "/announcements",
    "Consultations": "/consultations",
    "Publications": "/publications",
    "Statistics & Research": "/statistics-and-research",
}

HEADERS = {"User-Agent": "PressPaper MVP"}

JUNK_TITLES = [
    "view all",
    "sign up",
    "newsletter",
    "how we use your data",
    "clear filters",
    "about",
    "accessibility",
    "cookies",
]

# ================== SESSION ==================
st.session_state.setdefault("page", "home")
st.session_state.setdefault("category", None)
st.session_state.setdefault("article", None)
st.session_state.setdefault("saved", {})
st.session_state.setdefault("comments", {})
st.session_state.setdefault("feedback", {})

# ================== OPENAI ==================
def get_client():
    if "OPENAI_API_KEY" not in st.secrets:
        return None
    return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ================== DATA ==================
@st.cache_data(ttl=900)
def fetch_articles(category: str):
    url = BASE + CATEGORIES[category]
    r = requests.get(url, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")

    articles = []
    for a in soup.select("main a[href]"):
        title = (a.get_text() or "").strip()
        href = a.get("href") or ""

        if not title or len(title) < 15:
            continue
        if any(j in title.lower() for j in JUNK_TITLES):
            continue
        if not href.startswith("/"):
            continue

        articles.append(
            {
                "title": title,
                "url": urljoin(BASE, href),
                "organisation": "Welsh Government",
            }
        )

    # dedupe
    uniq = {}
    for a in articles:
        uniq[a["url"]] = a

    return list(uniq.values())[:40]


def fetch_text(url: str):
    r = requests.get(url, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    main = soup.find("main") or soup

    for t in main.select("script, style, nav, footer, header"):
        t.decompose()

    return " ".join(main.stripped_strings)


# ================== AI ==================
def summarise(text: str):
    client = get_client()
    if not client:
        return "_Summary unavailable (API key missing)._"

    prompt = f"""
Summarise this Welsh Government document.

Format:
Key points:
- bullet
- bullet
- bullet

Why it matters:
1–2 sentences.

TEXT:
{text[:6000]}
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You summarise official government documents."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return res.choices[0].message.content.strip()


def translate(text: str, lang: str):
    client = get_client()
    if not client:
        return "_Translation unavailable._"

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Translate faithfully without changing meaning."},
            {"role": "user", "content": f"Translate into {lang}:\n\n{text[:6000]}"},
        ],
        temperature=0.2,
    )
    return res.choices[0].message.content.strip()


def extract_topics(text: str):
    keywords = {
        "Health and social care": ["health", "nhs", "care"],
        "Public sector": ["government", "minister", "policy"],
        "Education": ["school", "education", "college"],
        "Environment": ["climate", "environment", "flood"],
        "Transport": ["transport", "road", "rail"],
    }

    found = []
    t = text.lower()
    for k, words in keywords.items():
        if any(w in t for w in words):
            found.append(k)
    return found or ["General"]


# ================== PAGES ==================
def page_home():
    st.title("📰 PressPaper")
    st.caption("Verified Welsh Government information — AI summarised")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Announcements", use_container_width=True):
            st.session_state.update(page="browse", category="Announcements")
        if st.button("Publications", use_container_width=True):
            st.session_state.update(page="browse", category="Publications")
    with c2:
        if st.button("Consultations", use_container_width=True):
            st.session_state.update(page="browse", category="Consultations")
        if st.button("Statistics & Research", use_container_width=True):
            st.session_state.update(page="browse", category="Statistics & Research")


def page_browse():
    st.button("← Back to categories", on_click=lambda: st.session_state.update(page="home"))
    st.title(st.session_state.category)

    articles = fetch_articles(st.session_state.category)

    main, right = st.columns([3.5, 1.5], gap="large")

    with right:
        st.subheader("Filter by")
        kw = st.text_input("Keywords")
        topic_filter = st.multiselect(
            "Topics",
            ["Health and social care", "Public sector", "Education", "Environment", "Transport", "General"],
        )
        org_filter = st.checkbox("Welsh Government", value=True)

        if st.button("View Saved Articles"):
            st.session_state.page = "saved"

    with main:
        for a in articles:
            text = fetch_text(a["url"])
            topics = extract_topics(text)

            if kw and kw.lower() not in a["title"].lower():
                continue
            if topic_filter and not set(topic_filter).intersection(topics):
                continue

            st.markdown(f"### {a['title']}")
            st.caption(" · ".join(topics) + " · Welsh Government")

            c1, c2, c3 = st.columns(3)
            c1.button(
                "Read",
                key=f"read_{a['url']}",
                on_click=lambda a=a: st.session_state.update(article=a, page="article"),
            )
            c2.link_button("Source", a["url"])
            if c3.button("Save", key=f"save_{a['url']}"):
                st.session_state.saved[a["url"]] = a

            st.divider()


def page_article():
    a = st.session_state.article
    st.button("← Back to results", on_click=lambda: st.session_state.update(page="browse"))
    st.title(a["title"])
    st.caption("Welsh Government")

    text = fetch_text(a["url"])

    tabs = st.tabs(["Summary", "Context", "Translation", "Original"])

    with tabs[0]:
        if st.button("Generate summary"):
            summary = summarise(text)
            st.session_state.article["summary"] = summary
        st.markdown(a.get("summary", "_No summary yet_"))

        st.subheader("Was this summary helpful?")
        c1, c2 = st.columns(2)
        if c1.button("👍", key="up"):
            st.session_state.feedback[a["url"]] = "helpful"
        if c2.button("👎", key="down"):
            st.session_state.feedback[a["url"]] = "not helpful"

        st.subheader("Comments")
        comment = st.text_area("Your notes")
        if st.button("Save comment"):
            st.session_state.comments[a["url"]] = comment
            st.success("Saved")

    with tabs[1]:
        st.markdown(
            f"**Publisher:** Welsh Government\n\n"
            f"This document represents official government communication."
        )

    with tabs[2]:
        lang = st.selectbox("Language", ["Hindi", "Welsh", "French", "Spanish"])
        if st.button("Translate"):
            st.markdown(translate(text, lang))

    with tabs[3]:
        st.text_area("Original text", text, height=500)


def page_saved():
    st.button("← Back", on_click=lambda: st.session_state.update(page="browse"))
    st.title("Saved articles")

    if not st.session_state.saved:
        st.info("No saved articles yet.")
        return

    for a in st.session_state.saved.values():
        st.markdown(f"### {a['title']}")
        st.link_button("Source", a["url"])
        st.divider()


# ================== ROUTER ==================
if st.session_state.page == "home":
    page_home()
elif st.session_state.page == "browse":
    page_browse()
elif st.session_state.page == "article":
    page_article()
elif st.session_state.page == "saved":
    page_saved()
