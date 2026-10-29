# ai.py - the one place HireOps talks to the local AI model, with safety limits
import json
import logging
import os
from dataclasses import asdict, dataclass

import httpx  # the web library ollama uses under the hood; we need its error types
import ollama
from pydantic import BaseModel, ValidationError

# Which local model to use; set HIREOPS_MODEL to try a bigger one (see Step 3.9)
MODEL = os.environ.get("HIREOPS_MODEL", "llama3.2")
# Longest wait for one answer, in seconds; set HIREOPS_TIMEOUT to change it
TIMEOUT = int(os.environ.get("HIREOPS_TIMEOUT", "180"))
# Most word-pieces (tokens) one answer may have; stops a model that never finishes
MAX_TOKENS = 2000
# How much text the model can hold at once (prompt + answer), in tokens. Ollama's
# default is 4096, too small for a job plus a full resume: it would silently cut off
# the start of the prompt, where the instructions are.
CONTEXT = 8192

# A Client is a connection to Ollama; without timeout= it would wait forever
client = ollama.Client(timeout=TIMEOUT)

logger = logging.getLogger(__name__)


# What one model call cost: Ollama reports these numbers with every answer
@dataclass
class Usage:
    step: str  # which question this was, e.g. "JobInsights"
    prompt_tokens: int  # word-pieces the model read (your prompt)
    output_tokens: int  # word-pieces the model wrote (its answer)
    seconds: float  # how long the call took
    attempt: int  # 1 = first try, 2 = the retry


# Every call is added here, in order. decode() reads the new entries after a run.
usage_log: list[Usage] = []


def record_usage(step, response, attempt):
    """Save the token counts and time of one answer, and write them to the log."""
    # getattr(..., 0) gives 0 if a field is missing; "or 0" also turns None into 0
    usage = Usage(
        step=step,
        prompt_tokens=getattr(response, "prompt_eval_count", 0) or 0,
        output_tokens=getattr(response, "eval_count", 0) or 0,
        # total_duration is in nanoseconds (billionths of a second)
        seconds=round((getattr(response, "total_duration", 0) or 0) / 1e9, 2),
        attempt=attempt,
    )
    usage_log.append(usage)
    # One JSON line per call: easy to search, and Log Analytics can chart it
    logger.info("ai_usage %s", json.dumps({"model": MODEL, **asdict(usage)}))
    return usage


class AIError(Exception):
    """The model was too slow, never finished, or gave an answer we can't use."""


def ask(prompt: str, shape: type[BaseModel], temperature: float = 0):
    """Ask the model to fill in `shape` (a pydantic class); return the filled object.

    For example, ask(prompt, JobInsights) returns a JobInsights object.
    """
    for attempt in range(2):  # a stuck or broken answer gets one more try
        # At temperature 0 a small model can repeat itself in a loop. On the second
        # try, a little randomness (0.5) usually breaks the loop.
        heat = temperature if attempt == 0 else max(temperature, 0.5)
        try:
            response = client.chat(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                format=shape.model_json_schema(),  # the exact JSON shape we want
                options={
                    "temperature": heat,
                    "num_predict": MAX_TOKENS,
                    "num_ctx": CONTEXT,
                    "repeat_penalty": 1.2,  # above 1 discourages repeating words
                },
            )
        except httpx.TimeoutException:
            raise AIError(f"{MODEL} took longer than {TIMEOUT} seconds") from None
        record_usage(shape.__name__, response, attempt + 1)  # retries cost tokens too
        # done_reason "length" means it hit MAX_TOKENS: the JSON is cut off, so retry
        if response.done_reason == "length":
            continue
        try:
            # Check the JSON against the blueprint and build the object
            return shape.model_validate_json(response.message.content)
        except ValidationError:  # broken JSON or a list over its cap: try again
            continue
    raise AIError(f"{MODEL} couldn't give a usable answer, even on a second try")
