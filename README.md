# HireOps

![CI](https://github.com/5hayam0hebbi/hireops/actions/workflows/ci.yml/badge.svg)

An SRE's toolkit for the job search: small, free, open-source tools that run on your own laptop. One new tool every week.

## Tool 1: JD Decoder (v0.1.0, prototype)

Give it a job description and your resume. It tells you:

- What the job really asks for: every skill it mentions (found by a local AI model, with no fixed keyword list), must-haves, nice-to-haves, seniority, years of experience and possible red flags
- Your match score: the share of the job's skills your resume mentions (calculated by plain rules, so it is repeatable and explainable)
- The skills the job asks for that your resume never mentions
- Three suggested resume bullets that use only what your resume already says, with a warning if the AI adds a number that isn't in your resume

### Example

    [paste the output of: python jd_decoder.py samples/job.txt -r samples/resume.md]

### How to run it

1. Install [Ollama](https://ollama.com/download), then run `ollama pull llama3.2`
2. `git clone https://github.com/<your-username>/hireops.git` and `cd hireops`
3. `python3 -m venv .venv`, then `source .venv/bin/activate`, then `pip install -r requirements.txt`
4. `python jd_decoder.py samples/job.txt --resume samples/resume.md`

Options: `--no-ai` (rules only, fast), `--json` (machine-readable output), `-h` (help). `skills.json` is your backup skills list, used with `--no-ai` or when Ollama isn't running.

### How the score works

The local AI model reads the job and lists every skill it asks for. Plain rules then look for each of those skills in your resume as a whole word, in any letter case, including plurals and common aliases (for example "led a team" counts as Leadership). The score is the share of the job's skills that your resume mentions, so you can always see why. Skills the word check misses go back to the AI, which may count one only if it quotes the exact words from your resume that prove it, and the code checks the quote is really there. With `--no-ai`, the backup list in `skills.json` is used instead.

### What the AI does and doesn't do

- It reads the job description, finds its skills and suggests resume bullets. It runs locally through Ollama.
- It is told never to invent experience, and the code checks every suggested bullet for numbers that aren't in your resume.
- Always read every suggested bullet before you use it.

### Privacy

Your resume and job files never leave your computer. The samples in this repo are fictional. Keep your real files in a `private/` folder, which `.gitignore` keeps out of Git.

### Tests

`pytest -v` runs [X] tests on the rule-based parts. GitHub Actions runs Ruff and the tests on every push.

### Limitations

- [one honest limitation you noticed, e.g. the model is slower on long postings]
- [another, e.g. a skill written differently in your resume can show as missing]

Next tool: Job Radar, new roles at your target companies every morning.