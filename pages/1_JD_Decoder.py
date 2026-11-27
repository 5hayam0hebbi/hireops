# pages/1_JD_Decoder.py - the JD Decoder page of the HireOps web app
import requests
import streamlit as st

import resume_edit as edit
from bullets import unsupported_numbers
from decoder import decode
from links import UnsupportedLink, job_from_link
from resume_files import KINDS, read_resume
from webtext import plain


def get_job_text(link, pasted):
    """The job's text: the pasted text if there is any, otherwise read from the link."""
    if pasted.strip():  # the text box always works, so it wins
        return pasted.strip()
    if not link.strip():
        return ""
    try:
        job = job_from_link(link)
    except UnsupportedLink as error:  # LinkedIn, Workday and other sites
        st.info(str(error))
        return ""
    # LookupError: an Ashby job that has closed (see fetch_ashby_job in boards.py)
    except (requests.RequestException, LookupError):  # no internet, closed job, typo
        st.warning("Couldn't read that link right now. Paste the job text instead.")
        return ""
    st.success(f'Read "{job["title"]}" from the {job["company"]} job board.')
    # Remembered for the new resume's file name, e.g. resume-northwind-senior-sre.docx
    st.session_state["job_name"] = f"{job['company']} {job['title']}"
    return job["description"]

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
    if decoded.usage:  # what the AI calls cost: tokens and time
        t = decoded.tokens()
        st.caption(
            f"AI usage: {t['calls']} calls · {t['prompt_tokens']:,} tokens read · "
            f"{t['output_tokens']:,} written · {t['seconds']} s"
        )
    insights = decoded.insights
    if insights:
        st.subheader(f"{insights.role_title} ({insights.seniority})")
        if insights.years_experience:
            st.write(f"Experience asked for: {insights.years_experience}+ years")
    label = "Skills the AI found" if decoded.used_ai else "Skills found (rules only)"
    st.write(f"**{label} ({len(decoded.wanted)}):** {', '.join(decoded.wanted)}")
    if insights and insights.not_required:
        st.caption(
            "Named but not required (not scored): " + ", ".join(insights.not_required)
        )

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
    parts = decoded.breakdown()
    if parts:  # only with the AI: it labels must-haves and nice-to-haves
        (must_have, must_all), (nice_have, nice_all) = parts["must"], parts["nice"]
        st.write(
            f"**Must-haves shown:** {must_have} of {must_all} · "
            f"**nice-to-haves:** {nice_have} of {nice_all} · "
            f"**weighted score:** {decoded.weighted_score()}%"
        )
    missing = result.missing()
    st.write(f"**Missing from your resume:** {', '.join(missing) or 'nothing'}")
    if decoded.gaps():
        st.write(
            "**Real gaps** (no proof in your resume; cover them in a cover letter "
            "or interview, not a bullet): " + ", ".join(decoded.gaps())
        )

    if decoded.by_meaning:
        st.write("**Possibly shown in other words** (check each line yourself):")
        for skill, line in decoded.by_meaning.items():
            st.markdown(f'- **{skill}**: "{plain(line)}"')
    if decoded.used_ai:
        st.write("**Suggested resume bullets** (check every word before using them):")
        if not decoded.bullets:
            st.caption(
                "None usable this time. Click Decode again, or try a bigger model."
            )
        for bullet in decoded.bullets:
            st.markdown(f"- {plain(bullet.text)}")
            if bullet.source:
                st.caption(f'Based on your line: "{plain(bullet.source)}"')
            if bullet.invented:
                st.warning(f"{', '.join(bullet.invented)} is not in your resume")
            for warning in bullet.warnings:
                st.warning(warning)
    if insights and insights.red_flags:
        st.write("**Possible red flags** (with the words from the posting):")
        for flag in insights.red_flags:
            st.markdown(f'- {plain(flag.concern)}: "{plain(flag.quote)}"')


st.title("JD Decoder")

def add_bullets(decoded):
    """Pick and edit bullets, choose where they go, and download a NEW resume copy."""
    name, data = st.session_state["resume_file"]  # saved when you clicked Decode
    resume_text = st.session_state["resume_text"]
    run = st.session_state["run"]  # changes on every Decode, so old boxes reset
    st.subheader("Add bullets to your resume")
    chosen, first_source = [], ""
    for number, bullet in enumerate(decoded.bullets, start=1):
        include = st.checkbox(f"Include bullet {number}", key=f"include_{run}_{number}")
        # value= is only the starting text: whatever you type in the box wins
        text = st.text_area(
            f"Bullet {number}", value=bullet.text, key=f"bullet_{run}_{number}"
        )
        # The same check as before, on YOUR edited words, every time the page runs
        invented = sorted(unsupported_numbers(text, resume_text))
        if invented:
            st.warning(f"{', '.join(invented)} is not in your resume")
        if include and text.strip():
            chosen.append(text.strip())
            first_source = first_source or bullet.source
    if not chosen:
        st.caption("Tick Include on a bullet to add it to a copy of your resume.")
        return

    places = edit.places_for(name, data, resume_text)
    where = st.selectbox(
        "Where should the bullets go?",
        range(len(places)),  # the choices are numbers 0, 1, 2...
        index=edit.suggested(places, first_source),  # the section of its source line
        format_func=lambda number: places[number].label,  # ...shown as labels
    )
    job_name = st.text_input(
        "Job name for the new file", value=st.session_state.get("job_name", "")
    )
    pdf_as = "docx"
    if name.lower().endswith(".pdf"):
        choice = st.radio(
            "A PDF can't be edited reliably. Save the updated copy as:",
            ["Word (.docx)", "Markdown (.md)"],
        )
        pdf_as = "md" if choice.startswith("Markdown") else "docx"
    new_data = edit.updated_resume(
        name, data, resume_text, places[where].start, chosen, pdf_as
    )
    file_name = edit.download_name(job_name, name, pdf_as)
    with st.expander("Preview the updated resume"):
        st.text(read_resume(file_name, new_data))  # st.text shows it exactly as is
    st.download_button(
        "Download updated resume",
        data=new_data,
        file_name=file_name,
        mime=edit.MIME[edit.output_kind(name, pdf_as)],
    )
    st.caption(f"Saves {file_name}. Your original file is never changed.")


st.caption(
    "Add a job and your resume, then click Decode. Everything stays on this computer."
)

link = st.text_input(
    "Job link (Greenhouse or Lever)", placeholder="https://job-boards.greenhouse.io/..."
)
pasted = st.text_area("Or paste the job text (works for any site)", height=200)
upload = st.file_uploader("Your resume (PDF, Word, .txt or .md)", type=KINDS)
use_ai = st.toggle(
    "Use the AI (Ollama)", value=True, help="Off = rules only: fast, no AI"
)

# st.button returns True only on the run right after you click it
if st.button("Decode", type="primary"):
    st.session_state.pop("job_name", None)  # forget the last job's name
    job_text = get_job_text(link, pasted)  # .strip() removes spaces and blank lines at both ends
    resume_text = get_resume_text(upload)
    if not job_text:
        st.warning("Add a job first: paste its text, or a Greenhouse or Lever link.")
    else:
        # st.status shows a box that fills with the progress lines while the AI works
        with st.status("Decoding...", expanded=True) as box:
            decoded = decode(job_text, resume_text, use_ai=use_ai, progress=st.write)
            box.update(label="Decoded", state="complete", expanded=False)
        # session_state keeps values between reruns, so the results stay on screen
        st.session_state["decoded"] = decoded
        st.session_state["job_text"] = job_text  # the Interview Coach page uses it
        st.session_state["resume_text"] = resume_text
        if resume_text:  # the file itself, for the updated copy
            st.session_state["resume_file"] = (upload.name, upload.getvalue())
        else:
            st.session_state.pop("resume_file", None)  # pop = remove, if it's there
        st.session_state["run"] = st.session_state.get("run", 0) + 1
        if decoded.insights and not st.session_state.get("job_name"):
            st.session_state["job_name"] = decoded.insights.role_title

if "decoded" in st.session_state:
    show(st.session_state["decoded"])
    if st.session_state["decoded"].bullets and "resume_file" in st.session_state:
        add_bullets(st.session_state["decoded"])