# jd_decoder.py - HireOps tool 1 (JD Decoder)
# The AI reads the job and finds its skills; plain rules check your resume for them.
import sys

from extract import extract
from matcher import MatchResult, find_skills


def read(path):
    """Return the whole text of a file."""
    with open(path) as f:
        return f.read()


def print_insights(insights):
    """Show what the AI found. insights is a JobInsights object from extract.py."""
    # Dot notation reads an object's attributes: insights.role_title
    print(f"Role: {insights.role_title} ({insights.seniority})")
    # ", ".join(list) glues the items into one string with commas between
    print(f"Skills the AI found ({len(insights.skills)}): {', '.join(insights.skills)}")
    print("Must-haves:")
    for item in insights.must_haves:
        print("  - " + item)
    print("Nice-to-haves:")
    for item in insights.nice_to_haves:
        print("  - " + item)
    print("Possible red flags:")
    for item in insights.red_flags:
        print("  - " + item)


def main():
    if len(sys.argv) < 2:
        print("Usage: python jd_decoder.py JOB_FILE [RESUME_FILE]")
        return

    job_text = read(sys.argv[1])
    insights = extract(job_text)  # the AI part: reads the job for meaning
    print_insights(insights)
    print()

    # The AI's list replaces the fixed list in skills.json
    wanted = insights.skills

    if len(sys.argv) > 2:  # a resume was given: the rules part
        resume_text = read(sys.argv[2])
        # Plain rules check the resume for each skill the AI found
        result = MatchResult(wanted=wanted, have=find_skills(resume_text, wanted))
        # result.score() calls the score method of the MatchResult object
        print(f"Match score: {result.score()}% ({len(result.have)} of {len(wanted)} skills)")
        print("Missing from your resume:")
        for skill in result.missing():
            print("  - " + skill)


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as error:
        print(f"Couldn't find the file {error.filename}. Check the name and try again.")
    except ConnectionError:
        print("Ollama isn't running. Open the Ollama app and try again.")