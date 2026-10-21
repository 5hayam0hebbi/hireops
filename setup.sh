#!/usr/bin/env bash
# setup.sh - get this computer ready to run HireOps (Mac or Linux)
# Run it from the hireops folder with:  bash setup.sh
# It's safe to run again: anything already done is skipped.

# Stop at the first error, treat unset variables as errors, and fail if any part of a pipe fails
set -euo pipefail

MODEL="llama3.2"  # the local AI model HireOps uses

# step prints a heading; have checks whether a command is installed
step() { printf '\n==> %s\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

# Work from the folder this script is in (the hireops folder), wherever it's run from
cd "$(dirname "$0")"

step "1/5 Python 3.10 or newer"
if ! have python3; then
  echo "Python 3 is missing. Install it from https://www.python.org/downloads/ and run this again."
  exit 1
fi
# The code uses features from Python 3.10, so check the version
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "You have $(python3 --version). Install 3.10 or newer from https://www.python.org/downloads/"
  exit 1
fi
echo "Found $(python3 --version)"

step "2/5 Ollama (runs the AI model on this computer)"
if ! have ollama; then
  echo "Ollama is missing. Install it from https://ollama.com/download, open it once, then run this again."
  exit 1
fi
# If Ollama isn't answering, start it and wait up to 30 seconds
if ! ollama list >/dev/null 2>&1; then
  if [ "$(uname)" = "Darwin" ]; then
    open -a Ollama  # on a Mac, open the Ollama app
  else
    nohup ollama serve >/dev/null 2>&1 &  # on Linux, start Ollama in the background
  fi
  echo "Starting Ollama..."
  for _ in $(seq 1 30); do
    if ollama list >/dev/null 2>&1; then break; fi
    sleep 1
  done
fi
if ! ollama list >/dev/null 2>&1; then
  echo "Ollama didn't start. Open the Ollama app yourself, then run this again."
  exit 1
fi
echo "Ollama is running"

step "3/5 The AI model ($MODEL)"
if ollama list | grep -q "^$MODEL"; then
  echo "Already downloaded"
else
  ollama pull "$MODEL"  # about 2 GB, only the first time
fi

step "4/5 Python box (.venv) and packages"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# Use the box's own Python, so nothing is installed outside it
.venv/bin/python -m pip install --upgrade pip --quiet
.venv/bin/python -m pip install -r requirements.txt --quiet
echo "Packages installed"

step "5/5 Quick check: run the tests"
.venv/bin/python -m pytest -q

printf '\nAll set. Each time you work on HireOps:\n'
printf '  source .venv/bin/activate\n'
printf '  python jd_decoder.py samples/job.txt -r samples/resume.md\n'