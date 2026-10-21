# ai.py - the one place HireOps talks to the local AI model, with safety limits
import os

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
        # done_reason "length" means it hit MAX_TOKENS: the JSON is cut off, so retry
        if response.done_reason == "length":
            continue
        try:
            # Check the JSON against the blueprint and build the object
            return shape.model_validate_json(response.message.content)
        except ValidationError:  # broken JSON or a list over its cap: try again
            continue
    raise AIError(f"{MODEL} couldn't give a usable answer, even on a second try")
