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
st.set_page_config(page_title="PressPaper", layout="wide")
init_db()

# ================= SESSION STATE =================
st.session_state.setdefault("page", "home")
st.session_state.setdefault("category", None)
st.session_state.setdefault("article_id", None)
st.session_state.setdefault("filters", {"kw": "", "topics": [], "orgs": []})
st.session_state.setdefault("notes", {})  # local notes (session only)
st.session_state.setdefault("summary_feedback", {})  # local feedback (session only)
st.session_state.setdefault("last_translation_lang", "Hindi")

# ================= OPENAI =================
@st.cache_resource
def get_client() -> OpenAI:
    """
    Cached OpenAI client.
    Uses Streamlit secrets if available; otherwise falls back to env var (if set).
    """
    key = None
    try:
        # Streamlit Cloud / local secrets.toml
        key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        key = None

    if not key:
        # Don’t crash the whole app: just disable AI buttons gracefully
        return None  # type: ignore

    return OpenAI(api_key=key)


def ai_available() -> bool:
    return get_client() is not None


# ================= HELPERS =================
def clean_text(text: str) -> str:
    if not text:
        return ""
    junk = [
        "Share this page",
        "via Facebook",
        "via X",
        "via Email",
        "How we use your data",
        "Cookies",
        "Accessibility",
    ]
    for j in junk:
        text = text.replace(j, "")
    return re.sub(r"\s+", " ", text).strip()


def generate_summary(text: str) -> str:
    """
    Better summarisation prompt than simple sentence splitting.
    """
    client = get_client()
    if client is None:
        return "_AI summary unavailable. Add OPENAI_API_KEY to Streamlit secrets._"

    text = clean_text(text)

    prompt = f"""
You are summarising a Welsh Government document for busy readers.

Write:
1) **Key points** (5 bullet points, each <= 18 words, factual)
2) **Who it affects** (1-2 bullets)
3) **Why it matters** (2 short sentences)

Rules:
- Do NOT include website junk like "Share this page"
- No speculation. If unclear, say "Not specified".
- Keep it concise and clean.

TEXT:
{text[:8000]}
""".strip()

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You summarise government documents accurately and clearly."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return res.choices[0].message.content.strip()


def generate_context(article: dict) -> str:
    """
    Lightweight context without needing an API call.
    """
    org = article.get("organisations") or "Not specified"
    published = article.get("published") or "Not specified"
    topics = article.get("topics") or "Not specified"

    return (
        f"**Publisher:** {org}\n\n"
        f"**Published:** {published}\n\n"
        f"**Topics:** {topics}\n\n"
        "This is an official Welsh Government / public sector document. "
        "Use it to understand policy, announcements, or service updates at the time of publication."
    )


def translate_text(text: str, target_lang: str) -> str:
    client = get_client()
    if client is None:
        return "_AI translation unavailable. Add OPENAI_API_KEY to Streamlit secrets._"

    text = clean_text(text)

    prompt = f"""
Translate this government document into {target_lang}.

Rules:
- Keep tone official.
- Preserve meaning; don’t add facts.
- Keep names, dates, and organisations unchanged.
- If the text is already in {target_lang}, return it as-is.

TEXT:
{text[:8000]}
""".strip()

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

    # Don’t allow sidebar to force jump while on article page (keeps flow stable)
    if nav.lower() != st.session_state.page and st.session_state.page != "article":
        st.session_state.page = nav.lower()


# ================= PAGES =================
def page_home():
    st.title("PressPaper")
    st.caption("Verified Welsh Government information — AI summarised")

    c1, c2 = st.columns(2)

    def pick_category(cat: str):
        st.session_state.category = cat
        st.session_state.page = "browse"

    with c1:
        st.button("Announcements", on_click=pick_category, args=("Announcements",), use_container_width=True)
        st.button("Publications", on_click=pick_category, args=("Publications",), use_container_width=True)
    with c2:
        st.button("Consultations", on_click=pick_category, args=("Consultations",), use_container_width=True)
        st.button("Statistics and Research", on_click=pick_category, args=("Statistics and Research",), use_container_width=True)


def page_browse():
    # Back button to Home
    if st.button("← Back to Home"):
        st.session_state.category = None
        st.session_state.page = "home"
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

        # Keep this list small & safe (you can expand later dynamically from DB)
        orgs = st.multiselect(
            "Organisations",
            ["Welsh Government", "NHS Wales", "Public Health Wales", "Senedd"],
            st.session_state.filters["orgs"],
        )

        cA, cB = st.columns(2)
        with cA:
            if st.button("Apply", use_container_width=True):
                st.session_state.filters = {"kw": kw, "topics": topics, "orgs": orgs}
        with cB:
            if st.button("Clear", use_container_width=True):
                st.session_state.filters = {"kw": "", "topics": [], "orgs": []}

    with left:
        articles = get_articles(
            category=st.session_state.category,
            kw=st.session_state.filters["kw"],
            topics=st.session_state.filters["topics"],
        )

        if not articles:
            st.info("No results.")
            return

        for a in articles:
            # client-side org filter (since DB function doesn’t accept orgs param)
            if st.session_state.filters["orgs"]:
                if (a.get("organisations") or "") not in st.session_state.filters["orgs"]:
                    continue

            st.markdown(f"### {a['title']}")
            st.caption(f"{a['published']} · {a['organisations']}")
            st.markdown(f"**Topics:** {a['topics'] or '—'}")

            b1, b2, b3 = st.columns([1, 1, 1])
            with b1:
                st.button("Read", key=f"r{a['id']}", on_click=open_article, args=(a["id"],))
            with b2:
                st.link_button("Source", a["url"])
            with b3:
                st.button(
                    "Unsave" if a["saved"] else "Save",
                    key=f"s{a['id']}",
                    on_click=toggle_save,
                    args=(a["id"],),
                )

            st.divider()


def page_article():
    article = get_article(st.session_state.article_id)
    if not article:
        st.session_state.page = "browse"
        return

    # Always visible back button (top)
    if st.button("← Back to results"):
        st.session_state.page = "browse"
        return

    st.title(article["title"])
    st.caption(f"{article['published']} · {article['organisations']}")

    st.button(
        "Unsave" if article["saved"] else "Save",
        on_click=toggle_save,
        args=(article["id"],),
    )

    tabs = st.tabs(["Summary", "Context", "Translation", "Original"])

    # -------- SUMMARY --------
    with tabs[0]:
        colA, colB = st.columns([1, 2])
        with colA:
            if st.button("Generate / Refresh", disabled=not ai_available()):
                with st.spinner("Summarising…"):
                    s = generate_summary(article["raw_text"])
                    update_text(article["id"], "summary", s)

        st.markdown(article["summary"] or "_No summary yet._")

        st.subheader("Was this summary helpful?")
        f1, f2 = st.columns(2)
        with f1:
            if st.button("👍 Helpful", key="sum_helpful"):
                st.session_state.summary_feedback[article["id"]] = "helpful"
                st.success("Thanks — noted.")
        with f2:
            if st.button("👎 Not helpful", key="sum_not_helpful"):
                st.session_state.summary_feedback[article["id"]] = "not helpful"
                st.info("Got it — we’ll improve it.")

        st.subheader("Comments & notes")
        note = st.text_area(
            "Your notes",
            value=st.session_state.notes.get(article["id"], ""),
            height=140,
        )
        if st.button("Save notes"):
            st.session_state.notes[article["id"]] = note
            st.success("Saved")

    # -------- CONTEXT --------
    with tabs[1]:
        if not article.get("context"):
            ctx = generate_context(article)
            update_text(article["id"], "context", ctx)
            article = get_article(st.session_state.article_id)  # refresh local
        st.markdown(article.get("context") or "_No context yet._")

    # -------- TRANSLATION --------
    with tabs[2]:
        lang = st.selectbox(
            "Target language",
            ["Hindi", "Welsh", "French", "Spanish", "German", "Arabic", "Urdu"],
            index=["Hindi", "Welsh", "French", "Spanish", "German", "Arabic", "Urdu"].index(
                st.session_state.last_translation_lang
            )
            if st.session_state.last_translation_lang in ["Hindi", "Welsh", "French", "Spanish", "German", "Arabic", "Urdu"]
            else 0,
        )
        st.session_state.last_translation_lang = lang

        if st.button("Translate", disabled=not ai_available()):
            with st.spinner(f"Translating to {lang}…"):
                tr = translate_text(article["raw_text"], lang)
                update_text(article["id"], "translation", tr)
                article = get_article(st.session_state.article_id)  # refresh local

        st.text_area(
            f"Translation ({lang})",
            value=article.get("translation") or "",
            height=260,
        )

        st.caption("Note: this stores the most recent translation in the database.")

    # -------- ORIGINAL --------
    with tabs[3]:
        st.text_area("Original text", article["raw_text"], height=500)


def page_saved():
    st.title("Saved articles")
    saved = get_saved()

    if not saved:
        st.info("You haven’t saved any articles yet.")
        return

    for a in saved:
        st.markdown(f"### {a['title']}")
        st.caption(f"{a['published']} · {a.get('organisations','')}")
        c1, c2 = st.columns(2)
        with c1:
            st.button("Read", key=f"sr{a['id']}", on_click=open_article, args=(a["id"],))
        with c2:
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
else:
    st.session_state.page = "home"
    page_home()