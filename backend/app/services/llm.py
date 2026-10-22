"""
One text-completion call, whichever provider is configured.

WHY THIS EXISTS
---------------
The generator and the judge both want the same thing: send a
system prompt and a user prompt, get text and a token count
back. They were written against OpenAI's `responses.create`,
which Gemini does not implement.

Gemini publishes an OpenAI-compatible endpoint, but it speaks
`chat.completions` - a different method with a different
response shape:

                    OpenAI responses      Gemini chat
    system prompt   instructions=         a system message
    answer          .output_text          .choices[0].message.content
    tokens          usage.input_tokens    usage.prompt_tokens

So this module hides that difference behind `complete()`, and
both callers stop caring which provider is behind it.

WHAT IS DELIBERATELY NOT ROUTED THROUGH HERE
--------------------------------------------
`app/agent/model.py` - the Week-7 agent loop. It does tool
calling, and the two providers disagree about the shape of a
tool call: OpenAI returns `function_call` items in `output`,
Gemini returns `tool_calls` on a message. The Week-8
trajectory eval and the Week-10 race both read the OpenAI
shape, and quietly changing it would invalidate numbers
already reported against it.

The agent loop is replayed in every eval, so it never needs a
live model anyway. It stays on OpenAI.

CHOOSING A PROVIDER
-------------------
    LLM_PROVIDER=openai     (default)
    LLM_PROVIDER=gemini     needs GEMINI_API_KEY

Set it in backend/.env. Nothing else changes.
"""

from dataclasses import dataclass

from app.config import (
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    GEMINI_MODEL,
    LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)


@dataclass
class Completion:
    """
    The normalised result. Both providers end up here.
    """

    text: str

    input_tokens: int = 0

    output_tokens: int = 0

    model: str = ""

    provider: str = ""


def active_model() -> str:
    """
    The model name to record on a trace.
    """

    return (
        GEMINI_MODEL
        if LLM_PROVIDER == "gemini"
        else OPENAI_MODEL
    )


def build_client():
    """
    An OpenAI SDK client pointed at the configured provider.

    Gemini is reached through its OpenAI-compatible endpoint,
    so the same SDK serves both and there is no second
    dependency to install.
    """

    from openai import OpenAI

    if LLM_PROVIDER == "gemini":

        if not GEMINI_API_KEY:

            raise RuntimeError(
                "LLM_PROVIDER=gemini but "
                "GEMINI_API_KEY is not set. Get a "
                "free key from "
                "https://aistudio.google.com/apikey "
                "and put it in backend/.env"
            )

        return OpenAI(
            api_key=GEMINI_API_KEY,
            base_url=GEMINI_BASE_URL,
        )

    if not OPENAI_API_KEY:

        raise RuntimeError(
            "OPENAI_API_KEY is not configured."
        )

    return OpenAI(api_key=OPENAI_API_KEY)


def complete(
    client,
    system_prompt: str,
    user_prompt: str,
) -> Completion:
    """
    Send one prompt, get text and token counts back.

    Routed by provider rather than by trying one API and
    falling back on an exception: a fallback would turn a
    misconfigured key into a silent provider switch, and a
    trace that names the wrong model is worse than an error.
    """

    if LLM_PROVIDER == "gemini":
        return _gemini(
            client,
            system_prompt,
            user_prompt,
        )

    return _openai(
        client,
        system_prompt,
        user_prompt,
    )


def _openai(
    client,
    system_prompt: str,
    user_prompt: str,
) -> Completion:

    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=system_prompt,
        input=user_prompt,
    )

    usage = getattr(response, "usage", None)

    return Completion(
        text=(
            getattr(response, "output_text", "")
            or ""
        ).strip(),
        input_tokens=getattr(
            usage,
            "input_tokens",
            0,
        )
        or 0,
        output_tokens=getattr(
            usage,
            "output_tokens",
            0,
        )
        or 0,
        model=OPENAI_MODEL,
        provider="openai",
    )


def _gemini(
    client,
    system_prompt: str,
    user_prompt: str,
) -> Completion:

    response = client.chat.completions.create(
        model=GEMINI_MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
    )

    usage = getattr(response, "usage", None)

    text = ""

    if getattr(response, "choices", None):
        text = (
            response.choices[0].message.content
            or ""
        )

    return Completion(
        # Gemini wraps JSON in a ```json fence far more often
        # than OpenAI does, and both callers json.loads() the
        # result. Stripping it here keeps that quirk in one
        # place rather than in each caller's error handler.
        text=strip_code_fence(text),
        input_tokens=getattr(
            usage,
            "prompt_tokens",
            0,
        )
        or 0,
        output_tokens=getattr(
            usage,
            "completion_tokens",
            0,
        )
        or 0,
        model=GEMINI_MODEL,
        provider="gemini",
    )


def strip_code_fence(text: str) -> str:
    """
    Remove a leading ```json fence if there is one.

    Returns the text unchanged when there is no fence, so it
    is safe to apply to any response.
    """

    cleaned = (text or "").strip()

    if not cleaned.startswith("```"):
        return cleaned

    lines = cleaned.split("\n")

    # Drop the opening fence line, which may be ``` or
    # ```json, and the closing one if present.
    lines = lines[1:]

    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]

    return "\n".join(lines).strip()
