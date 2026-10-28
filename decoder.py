# decoder.py - JD Decoder's engine: one decode() for the command line AND the web app
import json
from dataclasses import dataclass, field

from ai import MODEL, AIError
from bullets import bullet_warnings, suggest_bullets, unsupported_numbers
from evidence import find_by_meaning
from extract import JobInsights, extract
from matcher import MatchResult, find_skills


def load_skills(path="skills.json"):
    """Your backup skills list, used only when the AI is off or not running."""
    with open(path) as f:
        return json.load(f)


# One suggested bullet, plus any numbers in it that your resume never mentions,
# and plain-English warnings (numbers from another line, upgraded claims, gaps)
@dataclass
class Bullet:
    text: str
    invented: list[str]
    warnings: list[str] = field(default_factory=list)


# Everything one decode found. field(default_factory=list) gives each result its
# own new empty list (a plain = [] would share one list between all results).
@dataclass
class Decoded:
    wanted: list[str]  # the skills the job asks for
    insights: JobInsights | None = None  # what the AI read; None in rules-only mode
    result: MatchResult | None = None  # the match; None when there's no resume
    by_meaning: dict[str, str] = field(default_factory=dict)  # {skill: resume line}
    bullets: list[Bullet] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # messages for you, e.g. AI is off
    used_ai: bool = False

    def gaps(self) -> list[str]:
        """Skills the job wants with NO proof at all: not word for word, not by meaning.

        These are real gaps. Don't write bullets for them; cover them in a cover
        letter or interview, or close them by building something.
        """
        if not self.result:
            return []
        return [s for s in self.result.missing() if s not in self.by_meaning]

    def breakdown(self) -> dict:
        """How many must-haves and nice-to-haves your resume shows (incl. by meaning).

        For example {"must": (3, 5), "nice": (1, 2), "not_required": 6}.
        """
        if not self.insights or not self.result:
            return {}
        shown = set(self.result.have) | set(self.by_meaning)
        must, nice = self.insights.must_haves, self.insights.nice_to_haves
        return {
            "must": (len([s for s in must if s in shown]), len(must)),
            "nice": (len([s for s in nice if s in shown]), len(nice)),
            "not_required": len(self.insights.not_required),
        }

    def weighted_score(self) -> int:
        """Like best_score, but a must-have counts twice as much as a nice-to-have."""
        parts = self.breakdown()
        if not parts:
            return self.best_score()
        (must_have, must_all), (nice_have, nice_all) = parts["must"], parts["nice"]
        total = 2 * must_all + nice_all
        if not total:
            return 0
        return round((2 * must_have + nice_have) / total * 100)

    def best_score(self) -> int:
        """The score you'd have if every 'found by meaning' match is right."""
        if not self.result or not self.wanted:
            return 0
        found = len(self.result.have) + len(self.by_meaning)
        return round(found / len(self.wanted) * 100)


def say_nothing(message):
    """The default progress function: it ignores the message."""


def decode(job_text, resume_text="", use_ai=True, progress=say_nothing):
    """Decode a job and compare it with a resume. Never crashes if the AI is off.

    progress is a function that receives a short message before each slow AI step:
    the command line passes print, and the web app passes a function that shows it.
    """
    decoded = Decoded(wanted=[])

    # Step 1: the AI reads the job and finds its skills
    if use_ai:
        progress(f"1/3 {MODEL} is reading the job...")
        try:
            decoded.insights = extract(job_text)
            decoded.used_ai = True
        except ConnectionError:
            decoded.notes.append("Ollama isn't running, so this used rules only.")
        except AIError as error:
            decoded.notes.append(f"{error}, so this used rules only.")

    # The skills to check: the AI's list, or the backup list from skills.json
    if decoded.insights:
        decoded.wanted = decoded.insights.skills
    else:
        decoded.wanted = find_skills(job_text, load_skills())

    # No resume (empty or only spaces): stop here, with the job's skills only
    if not resume_text.strip():
        return decoded

    # Plain rules check the resume for each wanted skill, word for word
    have = find_skills(resume_text, decoded.wanted)
    decoded.result = MatchResult(wanted=decoded.wanted, have=have)
    if not decoded.used_ai:
        return decoded  # the meaning check and bullets need the AI

    # Step 2: the AI looks for missed skills written in other words
    progress(f"2/3 {MODEL} is checking your resume for other wording...")
    try:
        decoded.by_meaning = find_by_meaning(decoded.result.missing(), resume_text)
    except (ConnectionError, AIError) as error:
        decoded.notes.append(f"No meaning check this time: {error}")

    # Step 3: the AI suggests bullets; the code flags numbers it may have invented
    progress(f"3/3 {MODEL} is writing resume bullets...")
    try:
        gaps = decoded.gaps()
        for text in suggest_bullets(job_text, resume_text):
            invented = sorted(unsupported_numbers(text, resume_text))
            warnings = bullet_warnings(text, resume_text, gaps)
            decoded.bullets.append(Bullet(text, invented, warnings))
    except (ConnectionError, AIError) as error:
        decoded.notes.append(f"No bullet suggestions this time: {error}")
    return decoded