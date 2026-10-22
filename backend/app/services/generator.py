import json

from app.services.llm import (
    active_model,
    build_client,
    complete,
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

        # Built through the shim, so LLM_PROVIDER decides
        # which service this talks to. Raises here rather
        # than at first request if the chosen provider has
        # no key.
        self.client = build_client()

        self.model = active_model()

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

        completion = complete(
            self.client,
            self.system_prompt,
            user_prompt,
        )

        raw_text = completion.text

        # Reported so the caller's generation span
        # carries real token counts rather than an
        # estimate. Absent usage is recorded as zero,
        # never guessed.
        meta = {
            "prompt_version": (
                self.prompt_version
            ),
            "model": completion.model,
            "provider": completion.provider,
            "input_tokens": (
                completion.input_tokens
            ),
            "output_tokens": (
                completion.output_tokens
            ),
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