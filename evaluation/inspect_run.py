"""
Builds the inspection view.

Reads retrieval_results.json and writes a
side-by-side Markdown table of question,
what was retrieved, and the generated answer,
so a failure can be labelled from evidence
rather than from memory.

Retrieval labelling needs no LLM. Pass
--answers to also call the generator and label
generation failures, which does need a key.
"""

import json
import sys

from evaluation.evaluate_retrieval import (
    AUTHORITATIVE_STRATEGY,
    SCORE_K,
)


RESULTS_PATH = (
    "evaluation/retrieval_results.json"
)

OUTPUT_PATH = "evaluation/inspection.md"

PREVIEW_LENGTH = 160


def load_report() -> dict:

    with open(
        RESULTS_PATH,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


def classify(
    record: dict,
    answer: str | None,
) -> str:
    """
    The two failure kinds the week is about,
    plus the third one this app can produce.
    """

    best_rank = record["best_rank"]

    if best_rank is None or best_rank > SCORE_K:
        return "retrieval failure"

    if answer is None:
        return "retrieval ok"

    if "couldn't find" in answer:
        return "abstention failure"

    return "retrieval ok - check answer"


def flatten(text: str) -> str:

    return " ".join(
        text.split()
    )[:PREVIEW_LENGTH]


def render_record(
    record: dict,
    answer: str | None,
) -> list[str]:

    expected = record["expected"]

    # A reranked arm is ordered by rerank_score,
    # so that column has to be shown or the
    # cosine scores look out of order.
    reranked = any(
        item["rerank_score"] is not None
        for item in record["retrieved"]
    )

    lines = [
        f"### {record['question_id']} — "
        f"{record['question']}",
        "",
        f"- **Expected:** "
        f"{expected['policy_id']} "
        f"section {expected['section']}",
        f"- **Best rank:** "
        f"{record['best_rank']}",
        f"- **Hit@{SCORE_K}:** "
        f"{record['hit_at_k']}",
        f"- **Label:** "
        f"{classify(record, answer)}",
        "",
        "| Rank | Cosine | Rerank | Policy | Section | Text |"
        if reranked
        else "| Rank | Cosine | Policy | Section | Text |",
        "| --- | --- | --- | --- | --- | --- |"
        if reranked
        else "| --- | --- | --- | --- | --- |",
    ]

    for item in record["retrieved"]:

        expected_marker = (
            " **<-- expected**"
            if item["policy_id"]
            == expected["policy_id"]
            and item["section"]
            == expected["section"]
            else ""
        )

        rerank_column = (
            f"| {item['rerank_score']} "
            if reranked
            else ""
        )

        lines.append(
            f"| {item['rank']} "
            f"| {item['score']} "
            f"{rerank_column}"
            f"| {item['policy_id']} "
            f"| {item['section']}"
            f"{expected_marker} "
            f"| {flatten(item['preview'])} |"
        )

    lines.append("")

    if answer is not None:

        lines.extend(
            [
                "**Generated answer**",
                "",
                f"> {flatten(answer)}",
                "",
            ]
        )

    return lines


def generate_answers(
    records: list[dict],
) -> dict:
    """
    Only imported on demand, because the
    generator requires an API key.
    """

    from app.services.generator import (
        Generator,
    )
    from app.services.retriever import (
        Retriever,
    )

    generator = Generator()

    retriever = Retriever(
        AUTHORITATIVE_STRATEGY
    )

    answers = {}

    for record in records:

        results = retriever.retrieve(
            record["question"],
            top_k=SCORE_K,
        )

        if not retriever.has_good_match(
            results
        ):

            answers[
                record["question_id"]
            ] = (
                "I couldn't find information "
                "about this in the provided "
                "HR policy documents."
            )

            continue

        generated = generator.generate(
            question=record["question"],
            results=results,
        )

        answers[
            record["question_id"]
        ] = generated.get(
            "answer",
            "",
        )

        print(
            f"Answered "
            f"{record['question_id']}."
        )

    return answers


def main():

    report = load_report()

    with_answers = (
        "--answers" in sys.argv
    )

    lines = [
        "# Inspection View",
        "",
        f"Authoritative strategy: "
        f"`{AUTHORITATIVE_STRATEGY}`. "
        f"Scored at k={SCORE_K}.",
        "",
    ]

    for strategy, run in report[
        "runs"
    ].items():

        summary = run["summary"]

        lines.extend(
            [
                f"## {strategy}",
                "",
                f"hit@1 "
                f"{summary['hit_rate_at_1']} "
                f"· hit@{SCORE_K} "
                f"{summary[f'hit_rate_at_{SCORE_K}']} "
                f"· mrr {summary['mrr']} "
                f"· {run['indexed_chunks']} chunks",
                "",
            ]
        )

        answers = {}

        if (
            with_answers
            and strategy
            == AUTHORITATIVE_STRATEGY
        ):

            answers = generate_answers(
                run["records"]
            )

        for record in run["records"]:

            lines.extend(
                render_record(
                    record,
                    answers.get(
                        record["question_id"]
                    ),
                )
            )

    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            "\n".join(lines)
        )

    print(
        f"Wrote {OUTPUT_PATH}."
    )


if __name__ == "__main__":
    main()
