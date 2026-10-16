import json

from openai import OpenAI

from app.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
)
from app.services.prompts import (
    CURRENT_PROMPT_VERSION,
    get_prompt,
)


# Kept so existing importers still resolve. The text
# now lives in app/services/prompts.py, versioned, so
# a trace can say which one produced an answer.
SYSTEM_PROMPT = get_prompt("v1")


class Generator:

    def __init__(
        self,
        prompt_version: str = (
            CURRENT_PROMPT_VERSION
        ),
    ):
        """
        `prompt_version` is recorded on every trace
        this generator produces, so an answer can
        always be traced back to the text that wrote
        it. The Week-11 drill pins the old version
        deliberately to reproduce the failure.
        """

        self.prompt_version = prompt_version

        self.system_prompt = get_prompt(
            prompt_version
        )

        if not OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured."
            )

        self.client = OpenAI(
            api_key=OPENAI_API_KEY
        )

    def generate(
        self,
        question: str,
        results: list[dict],
    ) -> dict:

        if not results:
            return {
                "answer": (
                    "I couldn't find information "
                    "about this in the provided "
                    "HR policy documents."
                ),
                "sources": [],
            }

        context_parts = []

        for result in results:

            metadata = result["metadata"]

            context_parts.append(
                f"""
CHUNK_ID: {metadata.get('chunk_id')}
POLICY_ID: {metadata.get('policy_id')}
SECTION: {metadata.get('section')}
SOURCE_FILE: {metadata.get('source_file')}
REGION: {metadata.get('region')}
EFFECTIVE_DATE: {metadata.get('effective_date')}

CONTENT:
{result['text']}
"""
            )

        context = "\n---\n".join(
            context_parts
        )

        user_prompt = f"""
Use ONLY the following HR policy context.

CONTEXT:
{context}

QUESTION:
{question}

If the context does not support the answer,
say that the information is not available.
Do not guess.

Return JSON only.
"""

        response = self.client.responses.create(
            model=OPENAI_MODEL,
            instructions=self.system_prompt,
            input=user_prompt,
        )

        raw_text = response.output_text.strip()

        # Reported so the caller's generation span
        # carries real token counts rather than an
        # estimate. Absent usage is recorded as zero,
        # never guessed.
        usage = getattr(
            response,
            "usage",
            None,
        )

        meta = {
            "prompt_version": (
                self.prompt_version
            ),
            "input_tokens": getattr(
                usage,
                "input_tokens",
                0,
            )
            or 0,
            "output_tokens": getattr(
                usage,
                "output_tokens",
                0,
            )
            or 0,
        }

        try:
            data = json.loads(
                raw_text
            )
        except json.JSONDecodeError:

            return {
                "answer": (
                    "I couldn't safely produce a "
                    "structured answer from the "
                    "provided policy documents."
                ),
                "sources": [],
                "_meta": meta,
            }

        data["_meta"] = meta

        return data