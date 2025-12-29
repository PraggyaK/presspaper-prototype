from __future__ import annotations

import requests
import streamlit as st
from bs4 import BeautifulSoup
from openai import OpenAI
from urllib.parse import urljoin

# ---------------- CONFIG ----------------
st.set_page_config(
    page_title="PressPaper",
    layout="wide",
)

BASE = "https://www.gov.wales"

CATEGORIES = {
    "Announcements": "/announcements",
    "Consultations": "/consultations",
    "Publications": "/publications",
    "Statistics & Research": "/statistics-and-research",
}

HEADERS = {"User-Agent": "PressPaper MVP"}

# ---------------- OPENAI ----------------
def get_client():
    if "OPENAI_API_KEY" not in st.secrets:
        return None
    return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


# ---------------- DATA FETCH ----------------
@st.cache_data(ttl=900)
def fetch_articles(category: str):
    url = BASE + CATEGORIES[category]
    r = requests.get(url, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")

    articles = []
    for a in soup.select("main a[href]"):
        title = (a.get_text() or "").strip()
        href = a.get("href")

        if not title or len(title) < 10:
            continue
        if not href.startswith("/"):
            continue

        articles.append({
            "title": title,
            "url": urljoin(BASE, href),
            "organisation": "Welsh Government"
        })

    # remove duplicates
    seen = {}
    for a in articles:
        seen[a["url"]] = a

    return list(seen.values())[:30]


def fetch_article_text(url: str):
    r = requests.get(url, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")

    main = soup.find("main") or soup
    for tag in main.select("script, style, nav, footer, header"):
        tag.decompose()

    text = " ".join(main.stripped_strings)
    return text


# ---------------- AI ----------------
def summarize(text: str):
    client = get_client()
    if not client:
        return "_AI summary unavailable (API key not configured)._"

    prompt = f"""
Summarise this Welsh Government document.

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


# ---------------- SESSION ----------------
st.session_state.setdefault("page", "home")
st.session_state.setdefault("category", None)
st.session_state.setdefault("article", None)


# ---------------- UI ----------------
def page_home():
    st.title("PressPaper")
    st.caption("Verified Welsh Government updates — summarised in real time")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Announcements", use_container_width=True):
            st.session_state.category = "Announcements"
            st.session_state.page = "browse"
        if st.button("Publications", use_container_width=True):
            st.session_state.category = "Publications"
            st.session_state.page = "browse"

    with c2:
        if st.button("Consultations", use_container_width=True):
            st.session_state.category = "Consultations"
            st.session_state.page = "browse"
        if st.button("Statistics & Research", use_container_width=True):
            st.session_state.category = "Statistics & Research"
            st.session_state.page = "browse"


def page_browse():
    if st.button("← Back to Home"):
        st.session_state.page = "home"
        return

    st.title(st.session_state.category)

    articles = fetch_articles(st.session_state.category)

    if not articles:
        st.warning("No articles found.")
        return

    for a in articles:
        st.markdown(f"### {a['title']}")
        st.caption(a["organisation"])

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Read", key=a["url"]):
                st.session_state.article = a
                st.session_state.page = "article"
        with b2:
            st.link_button("Source", a["url"])

        st.divider()


def page_article():
    a = st.session_state.article

    if st.button("← Back to results"):
        st.session_state.page = "browse"
        return

    st.title(a["title"])
    st.caption(a["organisation"])

    with st.spinner("Loading article…"):
        text = fetch_article_text(a["url"])

    tabs = st.tabs(["Summary", "Original"])

    with tabs[0]:
        if st.button("Generate summary"):
            with st.spinner("Summarising…"):
                summary = summarize(text)
                st.markdown(summary)

    with tabs[1]:
        st.text_area("Original text", text, height=500)


# ---------------- ROUTER ----------------
if st.session_state.page == "home":
    page_home()
elif st.session_state.page == "browse":
    page_browse()
elif st.session_state.page == "article":
    page_article()
