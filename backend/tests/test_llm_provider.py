"""
The provider shim.

Two providers, one `complete()`. What matters is that the
response shapes are genuinely different and both arrive
normalised - and that a misconfigured provider fails loudly
rather than silently answering on the other one.
"""

import pytest

import app.services.llm as llm
from app.services.llm import (
    Completion,
    complete,
    strip_code_fence,
)


class FakeOpenAIResponse:
    """
    OpenAI's `responses.create` shape.
    """

    def __init__(self):
        self.output_text = "  the answer  "
        self.usage = type(
            "Usage",
            (),
            {
                "input_tokens": 500,
                "output_tokens": 40,
            },
        )()


class FakeOpenAIClient:

    def __init__(self):
        self.responses = type(
            "Responses",
            (),
            {
                "create": lambda _self, **kwargs: (
                    FakeOpenAIResponse()
                )
            },
        )()


class FakeGeminiResponse:
    """
    Gemini's `chat.completions` shape - different field
    names at every level.
    """

    def __init__(self, content="the answer"):

        message = type(
            "Message",
            (),
            {"content": content},
        )()

        self.choices = [
            type(
                "Choice",
                (),
                {"message": message},
            )()
        ]

        self.usage = type(
            "Usage",
            (),
            {
                "prompt_tokens": 500,
                "completion_tokens": 40,
            },
        )()


class FakeGeminiClient:

    def __init__(self, content="the answer"):

        self.captured = {}

        completions = type(
            "Completions",
            (),
            {
                "create": lambda _s, **kw: (
                    self.captured.update(kw)
                    or FakeGeminiResponse(content)
                )
            },
        )()

        self.chat = type(
            "Chat",
            (),
            {"completions": completions},
        )()


# ---------------- normalisation -------------------


def test_openai_shape_is_normalised(monkeypatch):

    monkeypatch.setattr(
        llm,
        "LLM_PROVIDER",
        "openai",
    )

    result = complete(
        FakeOpenAIClient(),
        "system",
        "user",
    )

    assert result.text == "the answer"
    assert result.input_tokens == 500
    assert result.output_tokens == 40
    assert result.provider == "openai"


def test_gemini_shape_is_normalised(monkeypatch):
    """
    Gemini reports prompt_tokens/completion_tokens where
    OpenAI reports input_tokens/output_tokens. Reading the
    wrong pair silently logs zero and the cost column lies.
    """

    monkeypatch.setattr(
        llm,
        "LLM_PROVIDER",
        "gemini",
    )

    result = complete(
        FakeGeminiClient(),
        "system",
        "user",
    )

    assert result.text == "the answer"
    assert result.input_tokens == 500
    assert result.output_tokens == 40
    assert result.provider == "gemini"


def test_the_system_prompt_becomes_a_message(
    monkeypatch,
):
    """
    OpenAI takes `instructions=`; Gemini has no such
    parameter and needs a system-role message. Dropping it
    would leave the model with no instructions at all - and
    it would still answer, which is the dangerous part.
    """

    monkeypatch.setattr(
        llm,
        "LLM_PROVIDER",
        "gemini",
    )

    client = FakeGeminiClient()

    complete(client, "SYSTEM TEXT", "USER TEXT")

    messages = client.captured["messages"]

    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "SYSTEM TEXT"
    assert messages[1]["role"] == "user"


# ---------------- the JSON fence ------------------


def test_a_json_fence_is_stripped(monkeypatch):
    """
    Both callers json.loads() the result, and Gemini wraps
    JSON in a ```json fence far more often than OpenAI does.
    Unstripped, the generator returns its "could not produce
    a structured answer" fallback for every request.
    """

    monkeypatch.setattr(
        llm,
        "LLM_PROVIDER",
        "gemini",
    )

    result = complete(
        FakeGeminiClient(
            '```json\n{"answer": "25 days"}\n```'
        ),
        "system",
        "user",
    )

    import json

    assert json.loads(result.text) == {
        "answer": "25 days"
    }


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"a": 1}', '{"a": 1}'),
        ('```\n{"a": 1}\n```', '{"a": 1}'),
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ("  plain text  ", "plain text"),
        ("", ""),
    ],
)
def test_strip_code_fence_leaves_plain_text_alone(
    raw,
    expected,
):

    assert strip_code_fence(raw) == expected


# ---------------- failing loudly -------------------


def test_gemini_without_a_key_raises(monkeypatch):
    """
    Not a silent fallback to OpenAI. A trace that names the
    wrong model is worse than an error, and a fallback would
    turn a typo'd env var into a provider switch nobody
    noticed.
    """

    monkeypatch.setattr(
        llm,
        "LLM_PROVIDER",
        "gemini",
    )

    monkeypatch.setattr(
        llm,
        "GEMINI_API_KEY",
        None,
    )

    with pytest.raises(RuntimeError) as error:
        llm.build_client()

    assert "GEMINI_API_KEY" in str(error.value)

    # The error says where to get one.
    assert "aistudio.google.com" in str(
        error.value
    )


def test_the_default_provider_is_openai():
    """
    Switching provider is opt-in. Weeks 4-11 reported
    numbers against OpenAI and a changed default would
    silently re-measure them.
    """

    from app.config import LLM_PROVIDER

    assert LLM_PROVIDER == "openai"


def test_the_agent_loop_is_not_routed_through_the_shim():
    """
    The Week-7 loop does tool calling, and the two providers
    disagree on the shape of a tool call. The Week-8
    trajectory eval and the Week-10 race both read OpenAI's
    `function_call` items.
    """

    import inspect

    from app.agent import model as agent_model

    source = inspect.getsource(agent_model)

    assert "services.llm" not in source
    assert "responses.create" in source
