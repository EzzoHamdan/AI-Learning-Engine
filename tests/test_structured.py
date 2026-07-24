"""Tests for llm/structured.py — the one JSON path all generation flows through.

Phase 4 replaced seven regex extraction chains with `generate_structured`. That
made this function the single point where malformed model output is either
recovered or turned into an honest failure, so its retry and fallback behavior
is worth pinning precisely.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from learning_engine.llm.client import GenerationFailed
from learning_engine.llm.structured import _extract_json, generate_structured
from learning_engine.models import MCQQuiz


class Tiny(BaseModel):
    name: str
    count: int


# --------------------------------------------------------------------------- #
# The lenient extractor
# --------------------------------------------------------------------------- #


def test_extracts_bare_json():
    assert _extract_json('{"a": 1}') == '{"a": 1}'


def test_extracts_from_a_fenced_block():
    content = 'Sure, here you go:\n```json\n{"a": 1}\n```\nHope that helps!'
    assert _extract_json(content) == '{"a": 1}'


def test_extracts_from_an_unfenced_block_with_prose_around_it():
    assert _extract_json('Here: {"a": 1} — done.') == '{"a": 1}'


def test_empty_response_is_a_generation_failure():
    with pytest.raises(GenerationFailed, match="Empty response"):
        _extract_json("   ")


def test_response_with_no_json_is_a_generation_failure():
    with pytest.raises(GenerationFailed, match="No JSON object"):
        _extract_json("I'm sorry, I can't help with that.")


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #


def test_valid_response_is_returned_as_the_schema_type(fake_llm):
    client = fake_llm({"name": "x", "count": 2})
    result = generate_structured(client, "m", "prompt", Tiny)
    assert isinstance(result, Tiny)
    assert (result.name, result.count) == ("x", 2)
    assert client.call_count == 1


def test_first_attempt_requests_native_structured_output(fake_llm):
    client = fake_llm({"name": "x", "count": 2})
    generate_structured(client, "m", "prompt", Tiny)
    assert client.calls[0].used_native_json_schema


def test_schema_is_appended_to_the_prompt(fake_llm):
    client = fake_llm({"name": "x", "count": 2})
    generate_structured(client, "m", "Summarize this", Tiny)
    prompt = client.last_prompt
    assert "Summarize this" in prompt
    assert "ONLY a single JSON object" in prompt
    assert '"count"' in prompt  # the JSON schema itself


def test_generation_params_are_forwarded(fake_llm):
    client = fake_llm({"name": "x", "count": 2})
    generate_structured(client, "model-x", "p", Tiny, temperature=0.15, max_tokens=321)
    call = client.calls[0]
    assert (call.model, call.temperature, call.max_tokens) == ("model-x", 0.15, 321)


def test_max_tokens_is_omitted_when_not_given(fake_llm):
    client = fake_llm({"name": "x", "count": 2})
    generate_structured(client, "m", "p", Tiny)
    assert client.calls[0].max_tokens is None


# --------------------------------------------------------------------------- #
# Recovery
# --------------------------------------------------------------------------- #


def test_provider_rejecting_response_format_falls_back_to_plain_json(fake_llm):
    """Small local models often 400 on json_schema; that must not be fatal."""
    client = fake_llm({"name": "x", "count": 2}, reject_response_format=True)
    result = generate_structured(client, "m", "p", Tiny)
    assert result.count == 2
    # Same attempt retried without the response_format argument.
    assert client.call_count == 2
    assert client.calls[0].response_format is not None
    assert client.calls[1].response_format is None


def test_invalid_json_is_retried_once_with_the_error_fed_back(fake_llm):
    client = fake_llm("not json at all", {"name": "recovered", "count": 7})
    result = generate_structured(client, "m", "p", Tiny)
    assert result.name == "recovered"
    assert client.call_count == 2
    assert "Your previous response was invalid" in client.calls[1].prompt


def test_schema_violation_is_retried_once(fake_llm):
    client = fake_llm({"name": "x"}, {"name": "x", "count": 1})  # `count` missing
    assert generate_structured(client, "m", "p", Tiny).count == 1
    assert client.call_count == 2


def test_retry_drops_native_structured_output(fake_llm):
    """Free-form recovers better once the model has already failed the schema."""
    client = fake_llm("garbage", {"name": "x", "count": 1})
    generate_structured(client, "m", "p", Tiny)
    assert client.calls[0].used_native_json_schema
    assert client.calls[1].response_format is None


# --------------------------------------------------------------------------- #
# Honest failure
# --------------------------------------------------------------------------- #


def test_two_bad_responses_raise_rather_than_inventing_content(fake_llm):
    """The Phase 4 promise: a failed generation is reported, never faked."""
    client = fake_llm("garbage", "still garbage")
    with pytest.raises(GenerationFailed, match="after retry"):
        generate_structured(client, "m", "p", Tiny)
    assert client.call_count == 2  # exactly one retry, no infinite loop


def test_transport_error_is_wrapped_as_generation_failed(fake_llm):
    client = fake_llm(ConnectionError("server went away"))
    with pytest.raises(GenerationFailed, match="LLM request failed"):
        generate_structured(client, "m", "p", Tiny)


def test_empty_quiz_still_validates_but_carries_no_questions(fake_llm):
    """An empty list is schema-valid; callers, not the parser, decide it's useless."""
    client = fake_llm({"questions": []})
    assert generate_structured(client, "m", "p", MCQQuiz).questions == []
