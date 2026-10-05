"""Streamlit UI for the AI Resume - Job Matcher (powered by Google Gemini).

Run with:  streamlit run app.py
"""
import datetime as dt

import streamlit as st

from config_loader import load_config
from file_utils import extract_text
from llm_client import LLMError
from matcher import ResumeMatcher, load_history, save_history

cfg = load_config()
st.set_page_config(page_title=cfg["app"]["title"], page_icon="📄", layout="wide")


@st.cache_resource
def get_matcher() -> ResumeMatcher:
    return ResumeMatcher()


def read_input(label: str, key: str) -> str:
    """Let the user upload a file or paste text. Returns the text."""
    tab_upload, tab_paste = st.tabs(["Upload file", "Paste text"])
    text = ""
    with tab_upload:
        f = st.file_uploader(
            f"{label} (PDF, DOCX, TXT)", type=["pdf", "docx", "txt"], key=f"{key}_file"
        )
        if f is not None:
            try:
                text = extract_text(f.name, f.getvalue())
                st.caption(f"Read {len(text):,} characters from {f.name}")
            except Exception as e:
                st.error(str(e))
    with tab_paste:
        pasted = st.text_area(f"{label} text", height=220, key=f"{key}_text")
    return text or pasted.strip()


def render_chips(items: list[str], color: str) -> None:
    if not items:
        st.caption("None")
        return
    html = " ".join(
        f"<span style='background:{color};padding:3px 10px;border-radius:12px;"
        f"margin:2px;display:inline-block;font-size:0.85rem'>{i}</span>"
        for i in items
    )
    st.markdown(html, unsafe_allow_html=True)


def show_results(r: dict) -> None:
    st.subheader(f"{r['candidate_name']}  →  {r['job_title']}")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Overall match", f"{r['match_score']}%")
    c2.metric("Skills", f"{r['score_breakdown']['skills']}%")
    c3.metric("Experience", f"{r['score_breakdown']['experience']}%")
    c4.metric("Education", f"{r['score_breakdown']['education']}%")
    c5.metric("Keywords", f"{r['score_breakdown']['keywords']}%")
    st.progress(r["match_score"] / 100, text=f"Verdict: {r['verdict']}")
    st.info(r["summary"])

    left, right = st.columns(2)
    with left:
        st.markdown("**✅ Matched skills**")
        render_chips(r["matched_skills"], "#d1fae5")
        st.markdown("**💪 Strengths**")
        for s in r["strengths"]:
            st.write(f"- {s}")
    with right:
        st.markdown("**❌ Missing skills**")
        render_chips(r["missing_skills"], "#fee2e2")
        st.markdown("**⚠️ Gaps**")
        for g in r["gaps"]:
            st.write(f"- {g}")

    st.markdown("**🔑 ATS keywords to add**")
    render_chips(r["ats_keywords_to_add"], "#dbeafe")
    st.markdown("**🛠️ How to improve your resume**")
    for i, tip in enumerate(r["improvement_tips"], 1):
        st.write(f"{i}. {tip}")


def main() -> None:
    st.title("📄 " + cfg["app"]["title"])
    st.caption(f"Powered by Google Gemini ({cfg['llm']['model']}). Get a match score, skill gaps, "
               "a cover letter and interview prep in seconds.")

    try:
        matcher = get_matcher()
    except LLMError as e:
        st.error(str(e))
        st.stop()

    with st.sidebar:
        st.header("History")
        if cfg["app"]["save_history"]:
            history = load_history()
            if not history:
                st.caption("No analyses yet.")
            for h in history[:8]:
                st.write(f"**{h['match_score']}%** · {h['candidate_name']} → {h['job_title']}")
                st.caption(h["time"])

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### 1. Your resume")
        resume = read_input("Resume", "resume")
    with col_b:
        st.markdown("### 2. Job description")
        job = read_input("Job description", "job")

    if st.button("Analyze match", type="primary", use_container_width=True):
        try:
            with st.spinner("Gemini is analyzing your resume..."):
                result = matcher.analyze(resume, job)
            st.session_state.update(result=result, resume=resume, job=job)
            st.session_state.pop("letter", None)
            st.session_state.pop("questions", None)
            if cfg["app"]["save_history"]:
                save_history({**{k: result[k] for k in ("match_score", "candidate_name", "job_title")},
                              "time": dt.datetime.now().strftime("%d %b %Y, %H:%M")})
        except (ValueError, LLMError) as e:
            st.error(str(e))

    if "result" in st.session_state:
        result = st.session_state["result"]
        st.divider()
        show_results(result)

        st.divider()
        b1, b2 = st.columns(2)
        if b1.button("✉️ Generate cover letter", use_container_width=True):
            try:
                with st.spinner("Writing cover letter..."):
                    st.session_state["letter"] = matcher.cover_letter(
                        st.session_state["resume"], st.session_state["job"], result)
            except LLMError as e:
                st.error(str(e))
        if b2.button("🎤 Generate interview questions", use_container_width=True):
            try:
                with st.spinner("Preparing interview questions..."):
                    st.session_state["questions"] = matcher.interview_questions(
                        st.session_state["resume"], st.session_state["job"])
            except LLMError as e:
                st.error(str(e))

        if "letter" in st.session_state:
            st.markdown("### Cover letter")
            st.text_area("Edit and copy", st.session_state["letter"], height=320)
            st.download_button("Download cover letter", st.session_state["letter"],
                               file_name="cover_letter.txt")
        if "questions" in st.session_state:
            st.markdown("### Interview preparation")
            for i, q in enumerate(st.session_state["questions"], 1):
                with st.expander(f"Q{i}. {q['question']}"):
                    st.write(f"**Why they ask:** {q.get('why_asked', '')}")
                    st.write(f"**Tip:** {q.get('tip', '')}")


main()
