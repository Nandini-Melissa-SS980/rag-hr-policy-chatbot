"""
One answering path, instrumented.

The API and the Week-11 drill both go through here,
so a trace captured in the drill has the same shape
as a trace captured in production. Two code paths
that log differently are two systems, and only one of
them is the one the complaint came from.

Stages, which are what cost is attributed to:

    retrieval   embed the question, search the index
    generation  the model call
    tools       nothing in this path today; the agent
                loop is where tools live. Present as a
                stage so the breakdown has a zero to
                show rather than a missing row.
"""

from app.observability import Recorder
from app.services.prompts import (
    CURRENT_PROMPT_VERSION,
)


TOP_K = 5


def describe_context(
    results: list[dict],
) -> list[dict]:
    """
    What retrieval served, recorded on the trace.

    Without this a wrong answer is ambiguous: it could
    be retrieval serving the wrong passage or the
    model ignoring the right one. With it, that is one
    hop.
    """

    described = []

    for rank, result in enumerate(
        results,
        start=1,
    ):

        metadata = result.get("metadata", {})

        described.append(
            {
                "rank": rank,
                "chunk_id": result.get(
                    "chunk_id",
                    "",
                ),
                "policy_id": metadata.get(
                    "policy_id",
                    "",
                ),
                "section": metadata.get(
                    "section",
                    "",
                ),
                "score": round(
                    result.get("score", 0.0),
                    4,
                ),
                # Carried so the API can build its
                # response from the logged context
                # rather than retrieving a second
                # time. A trace that does not
                # describe the request that actually
                # ran is worse than no trace.
                "source_file": metadata.get(
                    "source_file",
                    "",
                ),
                "region": metadata.get(
                    "region",
                    "",
                ),
                "effective_date": metadata.get(
                    "effective_date",
                    "",
                ),
            }
        )

    return described


def answer_question(
    question: str,
    retriever,
    generator,
    top_k: int = TOP_K,
    region: str | None = None,
    trace_id: str | None = None,
    labels: dict | None = None,
    path: str | None = None,
    started_at: str | None = None,
) -> tuple[dict, dict]:
    """
    Answer one question and log one trace.

    Returns (response, trace_dict). The caller gets
    the answer; the trace is already on disk.

    `generator` may be None, which is what happens on
    an unfunded key. The trace still records the
    retrieval span and the error, because a request
    that failed is exactly the kind a complaint is
    about.
    """

    prompt_version = getattr(
        generator,
        "prompt_version",
        CURRENT_PROMPT_VERSION,
    )

    recorder_kwargs = {
        "question": question,
        "prompt_version": prompt_version,
        "trace_id": trace_id,
        "labels": labels or {},
        "started_at": started_at,
    }

    if path is not None:
        recorder_kwargs["path"] = path

    with Recorder(**recorder_kwargs) as trace:

        with trace.span(
            "retrieve",
            "retrieval",
            top_k=top_k,
            region=region,
        ) as span:

            results = retriever.retrieve(
                question,
                top_k=top_k,
                region=region,
            )

            context = describe_context(results)

            span.attributes["returned"] = len(
                results
            )

            span.attributes["top_score"] = (
                context[0]["score"]
                if context
                else 0.0
            )

        trace.context_ids = [
            item["chunk_id"]
            for item in context
        ]

        trace.labels["context"] = context

        abstained = (
            not retriever.has_good_match(
                results
            )
        )

        trace.abstained = abstained

        if abstained:

            trace.answer = (
                "I couldn't find information "
                "about this in the provided HR "
                "policy documents."
            )

            return (
                {
                    "answer": trace.answer,
                    "sources": [],
                },
                trace.as_dict(),
            )

        if generator is None:

            trace.error = (
                "generator unavailable"
            )

            trace.answer = ""

            return (
                {
                    "answer": "",
                    "sources": [],
                },
                trace.as_dict(),
            )

        with trace.span(
            "generate",
            "generation",
            model=trace.model,
            prompt_version=prompt_version,
        ) as span:

            generated = generator.generate(
                question=question,
                results=results,
            )

            meta = generated.pop(
                "_meta",
                {},
            )

            span.input_tokens = meta.get(
                "input_tokens",
                0,
            )

            span.output_tokens = meta.get(
                "output_tokens",
                0,
            )

        trace.answer = generated.get(
            "answer",
            "",
        )

        trace.sources = generated.get(
            "sources",
            [],
        )

        return generated, trace.as_dict()
