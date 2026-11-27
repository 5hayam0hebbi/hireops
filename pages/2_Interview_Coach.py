# pages/2_Interview_Coach.py - the Interview Coach page of the HireOps web app
import streamlit as st

import coach
from ai import AIError
from webtext import plain


def show_feedback(feedback):
    """The four STAR scores side by side, the tip, and the tighter version."""
    st.write(f"**STAR score: {feedback.total()} of 8**")
    if feedback.total() >= 6:
        st.success("Strong structure: practise saying it out loud.")
    else:
        weakest = min(feedback.scores, key=feedback.scores.get)  # the lowest score
        st.info(f"Work on the {weakest} part first.")
    columns = st.columns(4)  # four columns side by side
    # zip pairs each column with one (part, score) item: Situation with the first...
    for column, (part, score) in zip(columns, feedback.scores.items(), strict=True):
        column.metric(part, f"{score}/2")
    st.write(f"**Tip:** {plain(feedback.tip)}")
    st.write("**A tighter version** (check every word: it must still be true):")
    st.markdown(f"> {plain(feedback.tighter)}")  # > shows it as a quote
    if feedback.invented:
        st.warning(f"{', '.join(feedback.invented)} is not in your answer")


st.title("Interview Coach")
st.caption(
    "Likely questions for a job, and feedback on your answers. "
    "Everything stays on this computer."
)

# The job you decoded on the JD Decoder page is filled in for you
job_text = st.text_area(
    "The job description",
    value=st.session_state.get("job_text", ""),
    height=200,
    help="Decode a job on the JD Decoder page and it appears here.",
)
use_ai = st.toggle(
    "Use the AI (Ollama)", value=True, help="Off = template questions, no AI"
)

if st.button("Get likely questions", type="primary"):
    if not job_text.strip():
        st.warning("Paste a job description first.")
    else:
        with st.status("Reading the job...", expanded=True) as box:
            found, notes = coach.questions_for(job_text, use_ai, progress=st.write)
            box.update(label="Questions ready", state="complete", expanded=False)
        st.session_state["questions"] = found
        st.session_state["coach_notes"] = notes
        st.session_state.pop("feedback", None)  # old feedback is for another job


questions = st.session_state.get("questions", [])
for note in st.session_state.get("coach_notes", []):
    st.info(note)
if questions:
    st.subheader("Likely questions")
    for number, question in enumerate(questions, start=1):
        st.markdown(
            f"{number}. {plain(question.text)} *({question.kind}: "
            f"{plain(question.skill)})*"
        )

    pick = st.selectbox(
        "Practise one",
        range(len(questions)),
        format_func=lambda number: questions[number].text,
    )
    question = questions[pick].text
    # key= gives each question its own box, so switching questions keeps your words
    answer = st.text_area(
        "Your answer, the way you'd say it", height=220, key=f"answer_{pick}"
    )
    if answer.strip():
        for note in coach.answer_notes(answer):  # plain rules, no AI
            st.caption(note)

    left, right = st.columns(2)
    if left.button("Get STAR feedback", disabled=not use_ai or not answer.strip()):
        try:
            with st.spinner("The AI is reading your answer..."):
                st.session_state["feedback"] = coach.star_feedback(question, answer)
        except (ConnectionError, AIError) as error:
            st.warning(f"No feedback this time: {error}. Is Ollama running?")
    if right.button("Save to my answer bank", disabled=not answer.strip()):
        count = coach.save_answer(question, answer)
        st.success(f"Saved: {count} in your bank, private/answers.json (never uploaded).")

    feedback = st.session_state.get("feedback")
    if feedback and feedback.question == question:  # only this question's feedback
        show_feedback(feedback)        