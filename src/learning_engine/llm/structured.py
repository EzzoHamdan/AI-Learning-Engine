"""Structured LLM output — one function replacing the seven regex JSON chains.

generate_structured() asks the model for JSON (native json_schema when the
provider supports it, otherwise a plain instruction), validates it against a
Pydantic schema, and retries ONCE by feeding the validation error back to the
model before raising GenerationFailed. The single lenient JSON extractor lives
here and nowhere else.

This module must not import Streamlit (architecture rule R1).
"""

from __future__ import annotations

import json
import re
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from learning_engine.llm.client import GenerationFailed

T = TypeVar("T", bound=BaseModel)

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def _extract_json(content: str) -> str:
    """Return a JSON string from a model response (the ONE lenient extractor).

    Tries the whole string, then a fenced ```json block, then the widest
    brace-delimited span. Raises GenerationFailed if nothing JSON-like is found.
    """
    content = (content or "").strip()
    if not content:
        raise GenerationFailed("Empty response from model")
    try:
        json.loads(content)
        return content
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK.search(content)
    if match:
        return match.group(1)
    start, end = content.find("{"), content.rfind("}")
    if start != -1 and end > start:
        return content[start : end + 1]
    raise GenerationFailed(f"No JSON object found in response: {content[:200]}")


def _call(client, model, prompt, temperature, max_tokens, response_format):
    kwargs: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if response_format is not None:
        kwargs["response_format"] = response_format
    resp = client.chat.completions.create(**kwargs)
    return (resp.choices[0].message.content or "").strip()


def generate_structured(
    client: OpenAI,
    model: str,
    prompt: str,
    schema: type[T],
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> T:
    """Generate output for `prompt` and validate it against `schema`.

    Raises GenerationFailed if the model still returns invalid output after one
    corrective retry.
    """
    schema_json = schema.model_json_schema()
    base_prompt = (
        f"{prompt}\n\nRespond with ONLY a single JSON object — no prose, no code "
        f"fences — matching this JSON schema:\n{json.dumps(schema_json)}"
    )
    native_format = {
        "type": "json_schema",
        "json_schema": {"name": schema.__name__, "schema": schema_json},
    }

    prompt_now = base_prompt
    response_format = native_format
    last_error = ""

    for _ in range(2):  # initial attempt + one corrective retry
        try:
            content = _call(client, model, prompt_now, temperature, max_tokens, response_format)
        except Exception:
            # Provider may reject response_format; retry the same call without it.
            try:
                content = _call(client, model, prompt_now, temperature, max_tokens, None)
            except Exception as exc:
                raise GenerationFailed(f"LLM request failed: {exc}") from exc

        try:
            return schema.model_validate_json(_extract_json(content))
        except (ValidationError, GenerationFailed, json.JSONDecodeError) as exc:
            last_error = str(exc)
            prompt_now = (
                f"{base_prompt}\n\nYour previous response was invalid:\n{last_error}\n"
                "Return corrected JSON only."
            )
            response_format = None  # free-form often recovers better on retry

    raise GenerationFailed(f"Schema validation failed after retry: {last_error}")
