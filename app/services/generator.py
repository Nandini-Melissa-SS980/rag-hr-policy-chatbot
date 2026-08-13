import json

from openai import OpenAI

from app.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
)


SYSTEM_PROMPT = """
You are an HR policy assistant.

Your job is to answer questions ONLY using the
provided HR policy context.

Rules:

1. Do not use outside knowledge.
2. Do not invent HR policies.
3. If the context does not contain enough information
   to answer the question, refuse to answer.
4. Every factual claim must have a source citation.
5. Citations must use the provided chunk_id,
   policy_id, and section.
6. Keep the answer concise.
7. Return valid JSON only.

Required JSON format:

{
  "answer": "string",
  "sources": [
    {
      "chunk_id": "string",
      "policy_id": "string",
      "section": "string"
    }
  ]
}
"""


class Generator:

    def __init__(self):

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
            instructions=SYSTEM_PROMPT,
            input=user_prompt,
        )

        raw_text = response.output_text.strip()

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
            }

        return data