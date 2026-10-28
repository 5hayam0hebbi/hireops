# app.py - the HireOps web app's home page. Start it with: streamlit run app.py
import streamlit as st

# The browser tab's title and icon; this must be the first st. command on the page
st.set_page_config(page_title="HireOps", page_icon="🧭")

st.title("HireOps")
st.write(
    "An SRE's toolkit for the job search: free, open source, and it runs on your own laptop."
)

st.subheader("Pages")
# page_link makes a clickable link to another page of this app
st.page_link(
    "pages/1_JD_Decoder.py",
    label="JD Decoder: what a job really asks for, and how your resume matches",
)
st.caption("Coming next: Job Radar, Interview Coach, Pipeline and Search SLOs.")

st.subheader("Your privacy")
st.write(
    "Your resume is read on this computer and never uploaded anywhere. "
    "The AI model runs on this computer too (Ollama). "
    "Job links are read only through Greenhouse's and Lever's public job-board APIs."
)