"""
The one place that talks to the API.

Both the agent and the workflow call the same model
through here, so the race compares two control flows
rather than two clients.

Returns a normalised shape:

    {
      "tool_calls": [{"call_id", "name", "arguments"}],
      "text": str | None,
      "input_tokens": int,
      "output_tokens": int,
    }
"""

import json

from openai import OpenAI

from app.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
)


def build_client() -> OpenAI:

    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured."
        )

    return OpenAI(
        api_key=OPENAI_API_KEY
    )


def parse_arguments(raw) -> dict:

    if isinstance(raw, dict):
        return raw

    try:
        return json.loads(raw or "{}")

    except json.JSONDecodeError:
        return {}


def read_usage(response) -> tuple[int, int]:

    usage = getattr(
        response,
        "usage",
        None,
    )

    if usage is None:
        return 0, 0

    return (
        getattr(
            usage,
            "input_tokens",
            0,
        )
        or 0,
        getattr(
            usage,
            "output_tokens",
            0,
        )
        or 0,
    )


def read_tool_calls(response) -> list[dict]:

    calls = []

    for item in getattr(
        response,
        "output",
        [],
    ) or []:

        if (
            getattr(item, "type", "")
            != "function_call"
        ):
            continue

        calls.append(
            {
                "call_id": getattr(
                    item,
                    "call_id",
                    "",
                ),
                "name": getattr(
                    item,
                    "name",
                    "",
                ),
                "arguments": parse_arguments(
                    getattr(
                        item,
                        "arguments",
                        "{}",
                    )
                ),
            }
        )

    return calls


def make_model_call(
    client: OpenAI | None = None,
    model: str = OPENAI_MODEL,
):
    """
    Returns the callable the loop and the workflow
    both use.
    """

    client = client or build_client()

    def model_call(
        instructions: str,
        items: list,
        tools: list | None = None,
    ) -> dict:

        kwargs = {
            "model": model,
            "instructions": instructions,
            "input": items,
        }

        if tools:
            kwargs["tools"] = tools

        response = client.responses.create(
            **kwargs
        )

        input_tokens, output_tokens = (
            read_usage(response)
        )

        return {
            "tool_calls": read_tool_calls(
                response
            ),
            "text": getattr(
                response,
                "output_text",
                "",
            ),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    return model_call
