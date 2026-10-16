"""
Captures traces for error analysis.

A trace is one complete request: the question, the
chunks that were fetched, and what the app answered
- with enough configuration recorded to replay it.

The sample is drawn randomly from question_pool.json
with a fixed seed, so it is reproducible and not
picked to flatter the app.

Generation failures are recorded rather than raised,
so the retrieval half of every trace survives even
when the model is unavailable.
"""

import json
import random

from app.config import (
    EMBEDDING_MODEL,
    OPENAI_MODEL,
)
from app.services.retriever import Retriever


POOL_PATH = "evaluation/question_pool.json"

TRACES_PATH = "evaluation/traces.jsonl"

SEED = 42

SAMPLE_SIZE = 20

# Matches what /chat serves, so the traces
# describe the real application.
STRATEGY = "structure_aware"

TOP_K = 3


def load_pool() -> list[dict]:

    with open(
        POOL_PATH,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


def sample_questions(
    pool: list[dict],
    size: int = SAMPLE_SIZE,
    seed: int = SEED,
) -> list[dict]:
    """
    A fair, reproducible sample.

    Sorted by id afterwards so the traces read in a
    stable order, which does not affect which
    questions were chosen.
    """

    chosen = random.Random(seed).sample(
        pool,
        size,
    )

    return sorted(
        chosen,
        key=lambda question: question["id"],
    )


def describe_retrieved(
    results: list[dict],
) -> list[dict]:
    """
    Full chunk text is kept, not a preview, because
    a trace has to be replayable.
    """

    described = []

    for rank, result in enumerate(
        results,
        start=1,
    ):

        metadata = result["metadata"]

        described.append(
            {
                "rank": rank,
                "chunk_id": result["chunk_id"],
                "policy_id": metadata.get(
                    "policy_id",
                    "",
                ),
                "section": metadata.get(
                    "section",
                    "",
                ),
                "source_file": metadata.get(
                    "source_file",
                    "",
                ),
                "score": round(
                    result["score"],
                    4,
                ),
                "text": result["text"],
            }
        )

    return described


def build_generator():
    """
    Returns the generator, or None with the reason
    it is unavailable.
    """

    try:

        from app.services.generator import (
            Generator,
        )

        return Generator(), None

    except Exception as error:

        return None, (
            f"{type(error).__name__}: {error}"
        )


def capture_trace(
    trace_id: str,
    question: dict,
    retriever: Retriever,
    generator,
    generator_error: str | None,
) -> dict:

    results = retriever.retrieve(
        question["question"],
        top_k=TOP_K,
    )

    abstained = not retriever.has_good_match(
        results
    )

    trace = {
        "trace_id": trace_id,
        "question_id": question["id"],
        "question": question["question"],
        "config": {
            "strategy": STRATEGY,
            "top_k": TOP_K,
            "embedding_model": EMBEDDING_MODEL,
            "generator_model": OPENAI_MODEL,
            "rerank": False,
        },
        "retrieved": describe_retrieved(
            results
        ),
        "abstained": abstained,
        "answer": None,
        "sources": [],
        "generation_error": None,
    }

    if abstained:

        trace["answer"] = (
            "I couldn't find information about "
            "this in the provided HR policy "
            "documents."
        )

        return trace

    if generator is None:

        trace[
            "generation_error"
        ] = generator_error

        return trace

    try:

        generated = generator.generate(
            question=question["question"],
            results=results,
        )

        trace["answer"] = generated.get(
            "answer",
            "",
        )

        trace["sources"] = generated.get(
            "sources",
            [],
        )

    except Exception as error:

        trace["generation_error"] = (
            f"{type(error).__name__}: {error}"
        )

    return trace


def main():

    pool = load_pool()

    questions = sample_questions(pool)

    retriever = Retriever(STRATEGY)

    generator, generator_error = (
        build_generator()
    )

    if generator_error:

        print(
            "Generator unavailable, capturing "
            f"retrieval only: {generator_error}"
        )

    traces = []

    for index, question in enumerate(
        questions,
        start=1,
    ):

        trace = capture_trace(
            f"T{index:02d}",
            question,
            retriever,
            generator,
            generator_error,
        )

        traces.append(trace)

        print(
            f"{trace['trace_id']} "
            f"{question['id']}: "
            f"{'abstained' if trace['abstained'] else 'answered'}"
        )

    with open(
        TRACES_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        for trace in traces:

            file.write(
                json.dumps(trace)
                + "\n"
            )

    answered = sum(
        1
        for trace in traces
        if trace["answer"]
        and not trace["generation_error"]
    )

    print(
        f"\nWrote {len(traces)} traces to "
        f"{TRACES_PATH} "
        f"({answered} with answers)."
    )


if __name__ == "__main__":
    main()
