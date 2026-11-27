# pages/3_Job_Radar.py - the Job Radar page of the HireOps web app
import streamlit as st

import radar
from resume_files import KINDS, read_resume

st.title("Job Radar")
st.caption(
    "New matching roles at your companies' public job boards, best match first. "
    "Edit radar_config.json to change the companies, titles and places."
)

config = radar.load_json("radar_config.json")
skills = radar.load_json("skills.json")
st.write(
    f"Watching **{len(config['companies'])} companies** for "
    f"{', '.join(config['titles'])} roles in {', '.join(config['locations'])}."
)

# Your resume: the one you used on the JD Decoder page, or upload one here
resume_text = st.session_state.get("resume_text", "")
upload = st.file_uploader("Your resume (or decode a job first)", type=KINDS)
if upload is not None:
    resume_text = read_resume(upload.name, upload.getvalue())
show_all = st.checkbox("Include roles I've seen before")

if st.button("Check the job boards now", type="primary"):
    if not resume_text:
        st.warning("Add your resume first, so each role gets a match score.")
    else:
        seen = radar.load_seen()
        with st.spinner("Reading job boards (about a minute)..."):
            found = radar.find_roles(
                config, resume_text, skills, seen=() if show_all else seen
            )
        st.session_state["radar"] = found  # (matches, alert_jobs, jobs read)


if "radar" in st.session_state:
    matches, alert_jobs, total = st.session_state["radar"]
    st.write(f"Read {total} open jobs: **{len(matches)} matching roles**.")
    # One row per role; a list of dictionaries becomes a table
    rows = [
        {
            "Match": f"{job['score']}%",
            "Company": job["company"],
            "Role": job["title"],
            "Location": job["location"],
            "Missing": ", ".join(job["missing"][:3]),
            "Link": job["url"],
        }
        for job in matches
    ]
    st.dataframe(
        rows,
        hide_index=True,
        # Show the Link column as clickable links, labelled "Open"
        column_config={"Link": st.column_config.LinkColumn(display_text="Open")},
    )
    if alert_jobs:
        st.subheader(f"From your job alerts ({len(alert_jobs)})")
        for job in alert_jobs:
            st.markdown(f"- {job['company']}: [{job['title']}]({job['url']})")
    if (matches or alert_jobs) and st.button("Mark these as seen"):
        seen = radar.load_seen()
        seen.update(job["id"] for job in matches + alert_jobs)
        radar.save_seen(seen)
        st.success("Done: tomorrow's check shows only roles that are new.")        