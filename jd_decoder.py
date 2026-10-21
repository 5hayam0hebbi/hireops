# jd_decoder.py - HireOps tool 1 (JD Decoder), version 0
# Reads a job description and lists the skills it asks for.
# Plain Python, no AI yet: the AI model joins in the next version.
import json
import sys


def load_skills(path="skills.json"):
    """Read the list of skills to look for from a JSON file."""
    with open(path) as f:
        return json.load(f)


def find_skills(text, skills):
    """Return the skills from the list that appear anywhere in the text."""
    text = text.lower()  # compare in lowercase so "Python" matches "python"
    found = []
    for skill in skills:
        if skill.lower() in text:
            found.append(skill)
    return found


def main():
    # sys.argv is the list of words typed after python3,
    # e.g. ["jd_decoder.py", "samples/job.txt"]
    if len(sys.argv) < 2:
        print("Usage: python3 jd_decoder.py JOB_FILE")
        return  # stop here

    with open(sys.argv[1]) as f:
        job_text = f.read()

    skills = load_skills()
    wanted = find_skills(job_text, skills)

    print(f"This job asks for {len(wanted)} skills from your list:")
    for skill in wanted:
        print("  - " + skill)


# Run main() only when this file is run directly, not when it's imported
if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as error:
        # error.filename is the name of the file that couldn't be found
        print(f"Couldn't find the file {error.filename}. Check the name and try again.")