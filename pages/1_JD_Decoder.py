# pages/1_JD_Decoder.py - the JD Decoder page of the HireOps web app
import streamlit as st

from decoder import decode
from resume_files import KINDS, read_resume


def get_resume_text(upload):
    """The resume's text, read on this computer. "" if there's no file or no text."""
    if upload is None:
        return ""
    try:
        # .name is the file's name; .getvalue() is its contents, as bytes
        text = read_resume(upload.name, upload.getvalue())
    except ValueError as error:
        st.error(str(error))
        return ""
    if not text:
        st.warning(
            "No text found in that file. If it's a scanned PDF, try the Word version."
        )
    return text


def show(decoded):
    """Show everything one decode found."""
    for note in decoded.notes:  # for example "Ollama isn't running..."
        st.info(note)
    insights = decoded.insights
    if insights:
        st.subheader(f"{insights.role_title} ({insights.seniority})")
        if insights.years_experience:
            st.write(f"Experience asked for: {insights.years_experience}+ years")
    label = "Skills the AI found" if decoded.used_ai else "Skills found (rules only)"
    st.write(f"**{label} ({len(decoded.wanted)}):** {', '.join(decoded.wanted)}")

    result = decoded.result
    if result is None:
        st.caption("Add your resume to see your match score.")
        return
    # Two columns side by side; .metric shows a big number with a label
    left, right = st.columns(2)
    left.metric(
        "Match score",
        f"{result.score()}%",
        help="Skills your resume names word for word",
    )
    right.metric("If the meaning matches are right", f"{decoded.best_score()}%")
    missing = result.missing()
    st.write(f"**Missing from your resume:** {', '.join(missing) or 'nothing'}")

    if decoded.by_meaning:
        st.write("**Possibly shown in other words** (check each line yourself):")
        for skill, line in decoded.by_meaning.items():
            st.markdown(f'- **{skill}**: "{line}"')
    if decoded.used_ai:
        st.write("**Suggested resume bullets** (check every word before using them):")
        if not decoded.bullets:
            st.caption(
                "None usable this time. Click Decode again, or try a bigger model."
            )
        for bullet in decoded.bullets:
            st.markdown(f"- {bullet.text}")
            if bullet.invented:
                st.warning(f"{', '.join(bullet.invented)} is not in your resume")
    if insights and insights.red_flags:
        st.write("**Possible red flags** (with the words from the posting):")
        for flag in insights.red_flags:
            st.markdown(f'- {flag.concern}: "{flag.quote}"')


st.title("JD Decoder")
st.caption(
    "Add a job and your resume, then click Decode. Everything stays on this computer."
)

pasted = st.text_area("Paste the job text", height=200)
upload = st.file_uploader("Your resume (PDF, Word, .txt or .md)", type=KINDS)
use_ai = st.toggle(
    "Use the AI (Ollama)", value=True, help="Off = rules only: fast, no AI"
)

# st.button returns True only on the run right after you click it
if st.button("Decode", type="primary"):
    job_text = pasted.strip()  # .strip() removes spaces and blank lines at both ends
    resume_text = get_resume_text(upload)
    if not job_text:
        st.warning("Paste the job text first.")
    else:
        # st.status shows a box that fills with the progress lines while the AI works
        with st.status("Decoding...", expanded=True) as box:
            decoded = decode(job_text, resume_text, use_ai=use_ai, progress=st.write)
            box.update(label="Decoded", state="complete", expanded=False)
        # session_state keeps values between reruns, so the results stay on screen
        st.session_state["decoded"] = decoded

if "decoded" in st.session_state:
    show(st.session_state["decoded"])