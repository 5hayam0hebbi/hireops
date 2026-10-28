# jd_decoder.py - HireOps tool 1 (JD Decoder), the command line
# The work happens in decoder.py; this file reads files and prints the results.
import argparse
import json
import logging

from ai import MODEL, AIError
from decoder import decode
from edits import suggest_edits

# A logger is a named "channel" for log messages; __name__ is this module's name
logger = logging.getLogger(__name__)


def read(path):
    """Return the whole text of a file."""
    with open(path) as f:
        return f.read()


def show_progress(message):
    """Print a progress line right away (flush=True), before the slow AI step starts."""
    print(message, flush=True)


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


def print_match(decoded):
    """Show the score, the missing skills, meaning matches and bullets."""
    result = decoded.result
    print(
        f"Match score: {result.score()}% ({len(result.have)} of {len(decoded.wanted)} skills)"
    )
    print("Missing from your resume:")
    for skill in result.missing():
        print("  - " + skill)
    if decoded.by_meaning:
        # The AI's matches can be wrong, so you judge them; they don't change the score
        print("Possibly shown in other words (check each line yourself):")
        for skill, line in decoded.by_meaning.items():
            print(f'  - {skill}: "{line[:120]}"')  # [:120] = first 120 characters
        print(
            f"If all of these are right, your score would be {decoded.best_score()}%."
        )
    if decoded.used_ai:
        print("\nSuggested resume bullets (check every word before using them):")
        if not decoded.bullets:
            print("  none usable this time: run it again, or try a bigger model.")
        for bullet in decoded.bullets:
            print("  - " + bullet.text)
            if bullet.invented:  # an empty list counts as False
                print(
                    f"    WARNING: {', '.join(bullet.invented)} is not in your resume"
                )


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
        if edit["invented"]:  # a number or name your resume never mentions
            print(f"      WARNING: {', '.join(edit['invented'])} is not in your resume")
        if edit["dropped"]:  # facts from your line that the rewrite left out
            print(f"      NOTE: the rewrite drops {', '.join(edit['dropped'])}")


def main():
    parser = argparse.ArgumentParser(
        description="Decode a job description and compare it with your resume."
    )
    parser.add_argument("job", help="path to a job description text file")
    parser.add_argument("-r", "--resume", help="path to your resume (text or Markdown)")
    parser.add_argument("--no-ai", action="store_true", help="rules only, skip the AI")
    parser.add_argument(
        "--json", action="store_true", help="print the match as JSON (needs --resume)"
    )
    args = parser.parse_args()

    logging.basicConfig(
        filename="hireops.log",
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logger.info(
        "Decoding %s (resume: %s, AI: %s)", args.job, args.resume, not args.no_ai
    )

    # --json without --resume can't work, so explain and stop
    if args.json and not args.resume:
        print("--json needs --resume")
        return

    job_text = read(args.job)
    resume_text = read(args.resume) if args.resume else ""
    # --json is for other programs, so it skips the progress lines and the AI
    use_ai = not (args.no_ai or args.json)
    decoded = decode(job_text, resume_text, use_ai=use_ai, progress=show_progress)

    for note in decoded.notes:  # for example "Ollama isn't running..."
        print(note)
        logger.warning(note)

    if args.json:  # machine-readable output for other tools, then stop
        data = {
            "job": args.job,
            "score": decoded.result.score(),
            "have": decoded.result.have,
            "missing": decoded.result.missing(),
        }
        print(json.dumps(data, indent=2))
        return

    if decoded.insights:
        print()
        print_insights(decoded.insights)
    print()

    if not decoded.result:  # no resume given
        print(f"Skills this job asks for: {', '.join(decoded.wanted)}")
        return

    print_match(decoded)
    logger.info("Match score %s%% for %s", decoded.result.score(), args.job)

    if decoded.used_ai:  # the extra AI step: edits to your resume lines
        print(f"\nExtra: {MODEL} is suggesting edits to your resume...", flush=True)
        try:
            missing = decoded.result.missing()
            print_edits(
                suggest_edits(job_text, resume_text, missing, decoded.by_meaning)
            )
        except (ConnectionError, AIError) as error:
            print(f"No edit suggestions this time: {error}")
            logger.warning("AI problem: %s", error)


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as error:
        print(f"Couldn't find the file {error.filename}. Check the name and try again.")
        logger.error("File not found: %s", error.filename)