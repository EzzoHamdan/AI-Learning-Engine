"""Shared test fixtures: a fake LLM client and the captured real-provider corpus.

`FakeLLM` duck-types the small slice of the OpenAI SDK the project actually uses
(`client.chat.completions.create(...) -> resp.choices[0].message.content`), so
generation code can be exercised end to end with no network and no mocking
library. It records every call, which is how the prompt-assembly and retry tests
assert on what was actually sent.

`fixture_text` reads `tests/fixtures/`, which holds RAW responses captured from a
real provider (see the module docstring in each generator test). Freezing real
output is the point: hand-written JSON only ever proves the schema matches
itself, while a real response catches the ways models actually deviate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


# --------------------------------------------------------------------------- #
# Fake LLM client
# --------------------------------------------------------------------------- #


@dataclass
class _Message:
    content: str | None


@dataclass
class _Choice:
    message: _Message


@dataclass
class _Response:
    choices: list[_Choice]


@dataclass
class RecordedCall:
    """One `chat.completions.create` invocation."""

    model: str
    prompt: str
    temperature: float | None = None
    max_tokens: int | None = None
    response_format: dict | None = None

    @property
    def used_native_json_schema(self) -> bool:
        return (self.response_format or {}).get("type") == "json_schema"


class FakeLLM:
    """A stand-in for `openai.OpenAI` that replays scripted responses.

    Each element of `responses` is either a string (returned as the message
    content) or an Exception (raised, to simulate a provider error). The last
    response repeats if the code calls more times than there are responses,
    which keeps single-response tests trivial.
    """

    def __init__(
        self,
        *responses: str | BaseException | dict,
        reject_response_format: bool = False,
    ) -> None:
        if not responses:
            raise ValueError("FakeLLM needs at least one response")
        self._responses: list[Any] = [
            json.dumps(r) if isinstance(r, dict) else r for r in responses
        ]
        # Mimics providers/models that 400 on `response_format=json_schema`.
        self.reject_response_format = reject_response_format
        self.calls: list[RecordedCall] = []

    # The SDK's namespaces are just attribute hops; this object is all three.
    @property
    def chat(self) -> FakeLLM:
        return self

    @property
    def completions(self) -> FakeLLM:
        return self

    def create(self, **kwargs: Any) -> _Response:
        call = RecordedCall(
            model=kwargs.get("model", ""),
            prompt=kwargs["messages"][0]["content"],
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens"),
            response_format=kwargs.get("response_format"),
        )
        self.calls.append(call)

        if self.reject_response_format and call.response_format is not None:
            raise RuntimeError("response_format is not supported by this model")

        index = min(len(self.calls) - 1, len(self._responses) - 1)
        response = self._responses[index]
        if isinstance(response, BaseException):
            raise response
        return _Response(choices=[_Choice(message=_Message(content=response))])

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def last_prompt(self) -> str:
        return self.calls[-1].prompt


@pytest.fixture
def fake_llm():
    """Factory so a test can build a FakeLLM with its own scripted responses."""
    return FakeLLM


# --------------------------------------------------------------------------- #
# Captured real-provider corpus
# --------------------------------------------------------------------------- #


@dataclass
class _Fixtures:
    """Lazy reader for tests/fixtures, with a clear skip when a file is absent."""

    directory: Path = field(default=FIXTURE_DIR)

    def text(self, name: str) -> str:
        path = self.directory / name
        if not path.exists():
            pytest.skip(f"missing captured fixture: {path.name}")
        return path.read_text(encoding="utf-8")

    def json(self, name: str) -> Any:
        return json.loads(self.text(name))

    def names(self) -> list[str]:
        if not self.directory.exists():
            return []
        return sorted(p.name for p in self.directory.iterdir() if p.is_file())


@pytest.fixture
def fixtures() -> _Fixtures:
    return _Fixtures()


# --------------------------------------------------------------------------- #
# Settings isolation
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _isolate_settings_cache():
    """Keep the cached settings singleton from leaking between test modules."""
    from learning_engine.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
