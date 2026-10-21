# jd_decoder.py - HireOps tool 1 (JD Decoder)
# The AI reads the job and finds its skills; plain rules check your resume for them.
import argparse
import json
import logging

from ai import MODEL, AIError
from matcher import MatchResult, find_skills

# A logger is a named "channel" for log messages; __name__ is this module's name
logger = logging.getLogger(__name__)


def load_skills(path="skills.json"):
    """Your backup skills list, used only when the AI is off or not running."""
    with open(path) as f:
        return json.load(f)


def read(path):
    """Return the whole text of a file."""
    with open(path) as f:
        return f.read()


def print_insights(insights):
    """Show what the AI found. insights is a JobInsights object from extract.py."""
    print(f"Role: {insights.role_title} ({insights.seniority})")
    if insights.years_experience:
        print(f"Experience asked for: {insights.years_experience}+ years")
    print(f"Skills the AI found ({len(insights.skills)}): {', '.join(insights.skills)}")
    print("Must-haves:")
    for item in insights.must_haves:
        print("  - " + item)
    print("Nice-to-haves:")
    for item in insights.nice_to_haves:
        print("  - " + item)
    print("Possible red flags (with the words from the posting):")
    if not insights.red_flags:
        print("  none found")
    for flag in insights.red_flags:
        print(f'  - {flag.concern}: "{flag.quote}"')


def print_edits(edits):
    """Show each suggested change with your own line, so you can judge it."""
    print("Suggested resume edits (nothing is changed for you; you decide):")
    if not edits:
        print("  none this time")
    labels = {
        "modify": "MODIFY your line:",
        "add": "ADD to your skills or summary:",
        "remove": "REMOVE your line:",
    }
    for edit in edits:
        if edit["action"] == "add":
            print(f'  {labels["add"]} "{edit["after"]}"')
        else:
            print(f'  {labels[edit["action"]]} "{edit["before"]}"')
        if edit["action"] == "modify":
            print(f'      to: "{edit["after"]}"')
        print(f"      why: {edit['reason']}")
        if edit["invented"]:  # a number your resume never mentions
            print(f"      WARNING: {', '.join(edit['invented'])} is not in your resume")


def main():
    parser = argparse.ArgumentParser(
        description="Decode a job description and compare it with your resume."
    )
    # A positional argument: required, and identified by its position
    parser.add_argument("job", help="path to a job description text file")
    # Optional arguments start with - or --; -r is the short form of --resume
    parser.add_argument("-r", "--resume", help="path to your resume (text or Markdown)")
    # store_true makes a flag: args.no_ai is True if you type --no-ai, else False
    parser.add_argument("--no-ai", action="store_true", help="rules only, skip the AI")
    parser.add_argument(
        "--json", action="store_true", help="print the match as JSON (needs --resume)"
    )
    args = parser.parse_args()

    # Send log messages at level INFO and above to hireops.log, with the time on each line
    logging.basicConfig(
        filename="hireops.log",
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    # Each %s is a slot that logging fills with the next value
    logger.info(
        "Decoding %s (resume: %s, AI: %s)", args.job, args.resume, not args.no_ai
    )

    job_text = read(args.job)

    insights = None  # None means "the AI hasn't answered (yet)"
    if not args.no_ai:
        from extract import extract  # only load the AI code when we use it

        # flush=True shows the line right away, before the slow AI call starts
        print(f"1/4 {MODEL} is reading the job...", flush=True)
        try:
            insights = extract(job_text)
        except ConnectionError:
            print("Ollama isn't running - using your skills.json list instead.\n")
            logger.warning("Ollama not running; used skills.json")
        except AIError as error:  # too slow, or it never finished
            print(f"{error} - using your skills.json list instead.\n")
            logger.warning("AI problem: %s", error)
            args.no_ai = True  # skip the other AI steps too, so you don't wait again

    # The skills to check: the AI's list, or the backup list from skills.json
    if insights:
        wanted = insights.skills
    else:
        wanted = find_skills(job_text, load_skills())

    # --json without --resume can't work, so explain and stop
    if args.json and not args.resume:
        print("--json needs --resume")
        return
    if args.json:  # machine-readable output for other tools, then stop
        result = MatchResult(wanted=wanted, have=find_skills(read(args.resume), wanted))
        data = {
            "job": args.job,
            "score": result.score(),
            "have": result.have,
            "missing": result.missing(),
        }
        # indent=2 puts each item on its own line, easy to read
        print(json.dumps(data, indent=2))
        return

    if insights:
        print_insights(insights)
        print()

    if args.resume:
        resume_text = read(args.resume)
        # Plain rules check the resume for each wanted skill, word for word
        result = MatchResult(wanted=wanted, have=find_skills(resume_text, wanted))
        by_meaning = {}  # skills the AI matched to a resume line: {skill: line}
        if insights:  # the AI is running, so check the missed skills for meaning
            from evidence import find_by_meaning

            print(
                f"2/4 {MODEL} is checking your resume for other wording...", flush=True
            )
            try:
                by_meaning = find_by_meaning(result.missing(), resume_text)
            except AIError as error:
                print(f"{error} - skipping the meaning check.")
                logger.warning("AI problem: %s", error)
            print()
        # The score counts only skills found word for word, so it stays reliable
        print(
            f"Match score: {result.score()}% ({len(result.have)} of {len(wanted)} skills)"
        )
        print("Missing from your resume:")
        for skill in result.missing():
            print("  - " + skill)
        if by_meaning:
            # The AI's matches can be wrong, so you judge them; they don't change the score
            print("Possibly shown in other words (check each line yourself):")
            # .items() gives each skill together with its resume line
            for skill, line in by_meaning.items():
                print(f'  - {skill}: "{line[:120]}"')  # [:120] = first 120 characters
            best = round((len(result.have) + len(by_meaning)) / len(wanted) * 100)
            print(f"If all of these are right, your score would be {best}%.")
        # %% writes a real % sign in a log message
        logger.info("Match score %s%% for %s", result.score(), args.job)
        if not args.no_ai:
            from bullets import suggest_bullets, unsupported_numbers
            from edits import suggest_edits

            try:
                print(f"\n3/4 {MODEL} is writing resume bullets...", flush=True)
                bullets = suggest_bullets(job_text, resume_text)
                print("Suggested resume bullets (check every word before using them):")
                if not bullets:
                    print(
                        "  none usable this time: the model gave titles or copied lines."
                    )
                    print("  Run it again, or try a bigger model (Step 3.9, Part F).")
                for bullet in bullets:
                    print("  - " + bullet)
                    invented = unsupported_numbers(bullet, resume_text)
                    if invented:  # an empty set counts as False
                        print(
                            f"    WARNING: {', '.join(sorted(invented))} is not in your resume"
                        )
            except ConnectionError:
                print("Ollama isn't running - no bullet suggestions this time.")
            except AIError as error:
                print(f"{error} - no bullet suggestions this time.")
                logger.warning("AI problem: %s", error)
            try:
                print(
                    f"\n4/4 {MODEL} is suggesting edits to your resume...", flush=True
                )
                print_edits(suggest_edits(job_text, resume_text, result.missing()))
            except (ConnectionError, AIError) as error:
                print(f"No edit suggestions this time: {error}")
                logger.warning("AI problem: %s", error)
    else:
        print(f"Skills this job asks for: {', '.join(wanted)}")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as error:
        print(f"Couldn't find the file {error.filename}. Check the name and try again.")
        logger.error("File not found: %s", error.filename)
