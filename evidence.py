# evidence.py - ask the AI whether your resume shows a skill in other words, with proof
import ollama
from pydantic import BaseModel

MODEL = "llama3.2"


# One answer: a skill and the exact resume words that prove it ("" if none)
class Evidence(BaseModel):
    skill: str
    quote: str


# The whole answer: a list of Evidence objects
class EvidenceList(BaseModel):
    found: list[Evidence]


PROMPT = """You check resumes honestly. For each skill below, decide whether the resume
shows that skill, even in different words. If it does, copy the exact words from the
resume that prove it, character for character, as one short phrase.
If the resume does not show the skill, use an empty quote "".
Never guess, and never write words that are not in the resume.

Skills:
{skills}

Resume:
{resume}"""


def normalize(text):
    """Lowercase and squeeze spaces, so small differences don't break the check."""
    # .split() breaks the text into words; " ".join puts them back with single spaces
    return " ".join(text.lower().split())


def verified(quote, resume_text):
    """True only if the quote really appears in the resume: the AI can't invent proof."""
    return bool(quote.strip()) and normalize(quote) in normalize(resume_text)


def find_by_meaning(missing, resume_text):
    """For skills the word check missed, return {skill: quote} for those the AI proved."""
    if not missing:  # nothing to check, so don't call the AI
        return {}
    response = ollama.chat(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": PROMPT.format(skills="\n".join(missing), resume=resume_text),
            }
        ],
        format=EvidenceList.model_json_schema(),
        options={"temperature": 0},
    )
    answer = EvidenceList.model_validate_json(response.message.content)

    # Look up our own spelling of each skill, whatever letter case the AI used
    by_lowercase = {skill.lower(): skill for skill in missing}
    proven = {}
    for item in answer.found:
        skill = by_lowercase.get(item.skill.strip().lower())
        # Keep it only if we asked about this skill AND the quote is really in the resume
        if skill and verified(item.quote, resume_text):
            proven[skill] = item.quote.strip()
    return proven