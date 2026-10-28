# pages/1_JD_Decoder.py - the JD Decoder page of the HireOps web app (first version)
import streamlit as st

from decoder import decode

st.title("JD Decoder")
st.caption("Paste a job and add your resume, then click Decode. Rules only for now.")

# A big text box; whatever you type or paste is stored in the variable pasted
pasted = st.text_area("Paste the job text", height=200)
# A drop zone for one file; type= limits which file endings it accepts
upload = st.file_uploader("Your resume (.txt or .md for now)", type=["txt", "md"])

# st.button returns True only on the run right after you click it
if st.button("Decode", type="primary"):
    if not pasted.strip():  # nothing but spaces counts as empty
        st.warning("Paste the job text first.")
    else:
        # .getvalue() is the file's bytes; .decode("utf-8") turns them into text
        resume_text = upload.getvalue().decode("utf-8") if upload else ""
        # The same engine as the command line, with the AI off for now
        decoded = decode(pasted, resume_text, use_ai=False)
        st.write(
            f"**Skills found ({len(decoded.wanted)}):** {', '.join(decoded.wanted)}"
        )
        if decoded.result:  # None when there's no resume
            # Two columns side by side, one number in each
            left, right = st.columns(2)
            left.metric("Match score", f"{decoded.result.score()}%")
            have, wanted = len(decoded.result.have), len(decoded.wanted)
            right.metric("Skills matched", f"{have} of {wanted}")
            missing = decoded.result.missing()
            # "or 'nothing'" shows the word nothing when the list is empty
            st.write(f"**Missing from your resume:** {', '.join(missing) or 'nothing'}")