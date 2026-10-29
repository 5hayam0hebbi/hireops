# HireOps: notes for AI coding agents (Claude Code)

## What this repo is
HireOps is an SRE's toolkit for the job search. Python 3.12. The AI is a local
model through Ollama (llama3.2). Never switch it to a paid API.

## Map
- ai.py: the only place that talks to the model (timeouts, retries, token logging)
- decoder.py: decode(), JD Decoder's engine, used by jd_decoder.py (command line)
  and pages/1_JD_Decoder.py (web app)
- boards.py, links.py: read Greenhouse, Lever and Ashby job boards
- matcher.py: rules-only skill matching
- radar.py: Job Radar (runs daily in GitHub Actions)
- agent.py: Job Scout agent (tools in SPECS and Tools, guardrails, the agent loop)
- eval_agent.py and evals/: grade the agent with the real model (run by hand, not in CI)
- test_*.py: pytest tests

## Commands
- Activate: source .venv/bin/activate
- Check (must pass before every commit): ruff check . && pytest -q
- Agent eval (needs Ollama running): python eval_agent.py

## Rules
- Show me a plan and wait for my go before editing any file.
- One small change at a time, always with a test.
- Tests never call the real model or a real job board: fake the model like
  FakeClient in test_agent.py, and fake boards with monkeypatch.
- New agent tools are read-only. Anything that writes must ask approve() first.
- Explain new code with short plain-English comments; I'm new to Python tooling.
- Never commit or read private/, shortlist.json, .env or *.tfvars.
- Never run git commit or git push; I do that after reviewing the diff.