"""
LLM-as-judge for the single policy-correctness
criterion. Everything a rule can check lives in
assertions.py instead.

The prompt is kept in a text file so judge_v1 and
judge_v2 can be diffed.
"""

import json

from app.services.llm import (
    active_model,
    build_client,
    complete,
)


PROMPT_PATHS = {
    "v1": "evaluation/judge_v1.txt",
    "v2": "evaluation/judge_v2.txt",
}


def load_prompt(
    version: str,
) -> str:

    if version not in PROMPT_PATHS:
        raise ValueError(
            f"Unknown judge version: {version}"
        )

    with open(
        PROMPT_PATHS[version],
        "r",
        encoding="utf-8",
    ) as file:

        return file.read()


def build_input(
    question: str,
    answer: str,
    retrieved: list[dict],
) -> str:

    context = "\n---\n".join(
        f"{item['policy_id']} section "
        f"{item['section']}\n{item['text']}"
        for item in retrieved
    )

    return f"""
POLICY CONTEXT:
{context}

QUESTION:
{question}

ANSWER TO GRADE:
{answer}

Return JSON only.
"""


class Judge:

    def __init__(
        self,
        version: str = "v1",
    ):

        self.version = version

        self.prompt = load_prompt(version)

        # Through the shim, so the judge follows
        # LLM_PROVIDER like the generator does. Judging
        # on one provider while answering on another
        # would make the agreement number meaningless.
        self.client = build_client()

        self.model = active_model()

    def judge(
        self,
        question: str,
        answer: str,
        retrieved: list[dict],
    ) -> dict:

        completion = complete(
            self.client,
            self.prompt,
            build_input(
                question,
                answer,
                retrieved,
            ),
        )

        raw_text = completion.text

        try:
            data = json.loads(raw_text)

        except json.JSONDecodeError:

            return {
                "verdict": "ERROR",
                "reason": (
                    "judge did not return JSON"
                ),
            }

        return {
            "verdict": data.get(
                "verdict",
                "ERROR",
            ),
            "reason": data.get(
                "reason",
                "",
            ),
        }
