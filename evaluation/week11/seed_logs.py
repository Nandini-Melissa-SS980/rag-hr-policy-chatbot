"""
Fill the log with a week of traffic, and plant one
bad answer in it.

    python -m evaluation.week11.seed_logs

The drill is only worth running against a haystack.
This writes ~200 requests across seven days, through
the same `answer_question` path the API uses, so
every row has the same shape a production row would.

THE PLANT
---------
One request quotes a notice period. The corpus has no
notice-period policy at all - that is a real property
of these documents, not something arranged for the
exercise - so the retriever returns the closest
chunks it has, which are about annual leave and
flexible working, and prompt v1 has nothing telling
the model to check the context is on topic. It
answers "30 days" out of a passage about carrying
leave over.

The plant is which request gets it, and the answer
text. The mechanism is the app's own.

WHERE THE ANSWERS COME FROM
---------------------------
The OpenAI key behind this project returns 429
insufficient_quota, as it has since Week 4. So the
generator is replayed: retrieval is real, the index
is real, the trace shape is real, the timings are
real, and the answer text is authored. Token counts
for the generation span are estimated from the real
payload at four characters per token, the same
estimate the Week-8 and Week-10 harnesses use.

`--live` swaps the real generator back in.
"""

import argparse
import json
import os
import random
from datetime import datetime, timedelta, timezone

from app.observability import REQUESTS_LOG
from app.services.answering import (
    answer_question,
)
from app.services.prompts import (
    CURRENT_PROMPT_VERSION,
)


POOL_PATH = "evaluation/question_pool.json"

# A week of traffic ending the day before the
# complaint lands.
DAYS = 7

REQUESTS_PER_DAY = 28

SEED = 20251110


# The planted request. Tuesday, mid-afternoon, one
# user among thousands.
PLANT = {
    "trace_id": "R-7f3c1a9e4d2b",
    "question": (
        "What notice period do I need to give "
        "if I resign?"
    ),
    "answer": (
        "You must give 30 days of notice when you "
        "resign. Notice must be submitted through "
        "the HR system and approved by your "
        "manager."
    ),
    "user": "u_4471",
    # v1 is the prompt without the on-topic rule.
    # This is the field that turns "the model
    # changed" into a one-hop diagnosis.
    "prompt_version": "v1",
    "day": 1,
    "hour": 14,
    "minute": 37,
}


def load_pool() -> list[dict]:

    with open(
        POOL_PATH,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


def estimate_tokens(text: str) -> int:

    return max(
        1,
        -(-len(text or "") // 4),
    )


class ReplayGenerator:
    """
    The generator, replayed.

    Answers from the retrieved passage so a logged
    answer is consistent with its own logged context
    ids - which is what makes the drill's diagnosis
    step real rather than decorative.
    """

    def __init__(
        self,
        prompt_version: str = (
            CURRENT_PROMPT_VERSION
        ),
    ):

        self.prompt_version = prompt_version

        self.forced_answer = None

    def generate(
        self,
        question: str,
        results: list[dict],
    ) -> dict:

        top = results[0]

        metadata = top["metadata"]

        if self.forced_answer is not None:

            answer = self.forced_answer

        else:

            # The first sentence of the retrieved
            # chunk, which is what a short policy
            # answer quotes.
            text = (top["text"] or "").strip()

            answer = text.split(". ")[0].strip()

            if len(answer) > 300:
                answer = (
                    answer[:297].rstrip() + "..."
                )

            if not answer.endswith("."):
                answer += "."

        sources = [
            {
                "chunk_id": top["chunk_id"],
                "policy_id": metadata.get(
                    "policy_id",
                    "",
                ),
                "section": metadata.get(
                    "section",
                    "",
                ),
            }
        ]

        # Counted off the real payload: the prompt,
        # every retrieved passage, and the question.
        context_text = "".join(
            result["text"] or ""
            for result in results
        )

        from app.services.prompts import (
            get_prompt,
        )

        input_tokens = (
            estimate_tokens(
                get_prompt(
                    self.prompt_version
                )
            )
            + estimate_tokens(context_text)
            + estimate_tokens(question)
        )

        return {
            "answer": answer,
            "sources": sources,
            "_meta": {
                "prompt_version": (
                    self.prompt_version
                ),
                "input_tokens": input_tokens,
                "output_tokens": (
                    estimate_tokens(answer)
                ),
            },
        }


def build_generator(live: bool):

    if not live:
        return ReplayGenerator(), None

    try:

        from app.services.generator import (
            Generator,
        )

        return Generator(), None

    except Exception as error:

        return (
            None,
            f"{type(error).__name__}: {error}",
        )


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "use the real generator instead of "
            "the replayed one"
        ),
    )

    parser.add_argument(
        "--path",
        default=REQUESTS_LOG,
    )

    arguments = parser.parse_args()

    # A fresh log each time, so the drill is timed
    # against a known haystack rather than an
    # accumulating one.
    if os.path.exists(arguments.path):
        os.remove(arguments.path)

    from app.services.retriever import Retriever

    retriever = Retriever("structure_aware")

    generator, error = build_generator(
        arguments.live
    )

    if error:
        raise SystemExit(
            f"--live unavailable: {error}"
        )

    pool = load_pool()

    random.seed(SEED)

    base = datetime(
        2025,
        11,
        3,
        9,
        0,
        0,
        tzinfo=timezone.utc,
    )

    users = [
        f"u_{number}"
        for number in range(4400, 4460)
    ]

    written = 0

    planted_at = None

    for day in range(DAYS):

        for index in range(REQUESTS_PER_DAY):

            case = random.choice(pool)

            started = base + timedelta(
                days=day,
                hours=random.randint(0, 8),
                minutes=random.randint(0, 59),
                seconds=random.randint(0, 59),
            )

            answer_question(
                case["question"],
                retriever,
                generator,
                labels={
                    "user": random.choice(
                        users
                    ),
                    "question_id": case["id"],
                },
                path=arguments.path,
                started_at=started.isoformat(),
            )

            written += 1

    # ---- the plant --------------------------------
    #
    # Same code path, same log file, one authored
    # answer and the old prompt version.
    planted = base + timedelta(
        days=PLANT["day"],
        hours=PLANT["hour"] - 9,
        minutes=PLANT["minute"],
    )

    planted_at = planted.isoformat()

    if isinstance(generator, ReplayGenerator):

        generator.forced_answer = PLANT[
            "answer"
        ]

        generator.prompt_version = PLANT[
            "prompt_version"
        ]

    answer_question(
        PLANT["question"],
        retriever,
        generator,
        labels={
            "user": PLANT["user"],
            "question_id": "PLANT",
        },
        trace_id=PLANT["trace_id"],
        path=arguments.path,
        started_at=planted_at,
    )

    if isinstance(generator, ReplayGenerator):

        generator.forced_answer = None

        generator.prompt_version = (
            CURRENT_PROMPT_VERSION
        )

    written += 1

    print(
        f"Wrote {written} requests to "
        f"{arguments.path}."
    )

    print(
        "One of them quotes a notice period. The "
        "complaint will say only: \"an employee "
        "said it quoted the wrong notice period, "
        "maybe Tuesday\"."
    )


if __name__ == "__main__":
    main()
