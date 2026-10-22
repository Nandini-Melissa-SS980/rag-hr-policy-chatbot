"""
Is the configured model provider actually reachable?

    python -m scripts.check_provider

Answers three questions in order, because they fail
differently and the fix is different each time:

    1. which provider is configured, and is its key present
    2. does the key have the shape that provider issues
    3. does a real one-token call succeed

Worth its own script because the alternative is restarting
the server and reading a 502 in the browser, which tells you
something is wrong and not what.
"""

import sys

from app.config import (
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    GEMINI_MODEL,
    LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)
from app.services.llm import build_client, complete


def masked(value: str) -> str:

    if not value:
        return "(not set)"

    return f"{value[:6]}...{value[-4:]} ({len(value)} chars)"


def main():

    print(f"LLM_PROVIDER : {LLM_PROVIDER}")

    if LLM_PROVIDER == "gemini":

        print(f"model        : {GEMINI_MODEL}")
        print(f"endpoint     : {GEMINI_BASE_URL}")
        print(
            f"GEMINI_API_KEY: {masked(GEMINI_API_KEY)}"
        )

        if not GEMINI_API_KEY:

            print(
                "\nNo key. Get one free at "
                "https://aistudio.google.com/apikey"
            )

            return 1

        # A Gemini API key starts with AIza. An OAuth
        # token (AQ....) is a different credential and is
        # rejected with a confusing NotFoundError, so it is
        # worth naming before the call rather than after.
        if not GEMINI_API_KEY.startswith("AIza"):

            print(
                "\nWARNING: a Gemini API key starts "
                "with 'AIza'. This looks like an OAuth "
                "token or a key for something else, and "
                "the API will reject it.\n"
                "Create one at "
                "https://aistudio.google.com/apikey "
                "-> Create API key."
            )

    else:

        print(f"model        : {OPENAI_MODEL}")
        print(
            f"OPENAI_API_KEY: {masked(OPENAI_API_KEY)}"
        )

    print("\nCalling the model...")

    try:
        client = build_client()

    except Exception as error:

        print(f"  client failed: {error}")

        return 1

    try:

        result = complete(
            client,
            "Reply with the single word: ok",
            "ping",
        )

    except Exception as error:

        name = type(error).__name__

        print(f"  FAILED: {name}")

        detail = str(error)

        print(f"  {detail[:300]}")

        # The three failures worth naming, because each has
        # a different fix and the raw message says none of
        # them.
        if "NotFound" in name or "404" in detail:

            print(
                "\n  A 404 here usually means the key is "
                "not a Gemini API key, or the model name "
                f"'{GEMINI_MODEL}' is not available to "
                "it. Check the key starts with AIza, and "
                "try GEMINI_MODEL=gemini-3.8-flash."
            )

        elif (
            "RateLimit" in name
            or "429" in detail
        ):

            print(
                "\n  Quota exhausted. On OpenAI that is "
                "billing; on Gemini's free tier it "
                "resets daily."
            )

        elif (
            "Authentication" in name
            or "401" in detail
        ):

            print(
                "\n  The key was rejected. Check it was "
                "pasted whole, with no quotes or spaces."
            )

        return 1

    print(
        f"  OK  provider={result.provider} "
        f"model={result.model}"
    )

    print(f"  reply: {result.text[:60]!r}")

    print(
        f"  tokens: {result.input_tokens} in, "
        f"{result.output_tokens} out"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
