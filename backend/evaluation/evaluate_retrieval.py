import json

from app.config import (
    EMBEDDING_MODEL,
    RERANK_MODEL,
)
from app.services.retriever import (
    RERANK_POOL_MULTIPLIER,
    Retriever,
)
from evaluation.metrics import (
    hit_rate_at_k,
    mrr,
    ranks_within_k,
    recall_at_k,
)


# Retrieve a wide pool, score a narrow one.
# This lets a single run report @1 / @3 / @5
# and shows the rank a missed chunk did reach,
# which is what separates a reranking problem
# from a retrieval problem.
CANDIDATE_K = 10

SCORE_K = 3

REPORT_KS = [1, 3, 5]

# Only structure_aware carries trustworthy
# section labels. See notes in the report.
AUTHORITATIVE_STRATEGY = "structure_aware"

# Baseline and change measured in one run, on
# one frozen harness, so the delta cannot drift.
ARMS = [
    {
        "name": "basic",
        "strategy": "basic",
        "rerank": False,
    },
    {
        "name": "structure_aware",
        "strategy": "structure_aware",
        "rerank": False,
    },
    {
        "name": "structure_aware_rerank",
        "strategy": "structure_aware",
        "rerank": True,
    },
]

BASELINE_ARM = "structure_aware"

CHANGED_ARM = "structure_aware_rerank"

PREVIEW_LENGTH = 300


def load_questions() -> list[dict]:

    with open(
        "evaluation/questions.json",
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


def target_key(
    policy_id: str,
    section: str,
) -> str:

    return f"{policy_id}|{section}"


def expected_targets(
    question: dict,
) -> list[str]:
    """
    Supports one expected target today and a
    list of them without a schema change.
    """

    expected = question["expected"]

    if isinstance(expected, list):
        entries = expected
    else:
        entries = [expected]

    return [
        target_key(
            entry["policy_id"],
            entry["section"],
        )
        for entry in entries
    ]


def match_ranks(
    retrieved: list[dict],
    targets: list[str],
) -> dict[str, int]:
    """
    Best one-based rank each expected target
    was retrieved at.
    """

    matched = {}

    for rank, result in enumerate(
        retrieved,
        start=1,
    ):

        metadata = result["metadata"]

        key = target_key(
            metadata.get(
                "policy_id",
                "",
            ),
            metadata.get(
                "section",
                "",
            ),
        )

        if key in targets and key not in matched:
            matched[key] = rank

    return matched


def describe_retrieved(
    retrieved: list[dict],
) -> list[dict]:

    described = []

    for rank, result in enumerate(
        retrieved,
        start=1,
    ):

        metadata = result["metadata"]

        described.append(
            {
                "rank": rank,
                "score": round(
                    result["score"],
                    4,
                ),
                # Present only on a reranked arm.
                # Without it the table reads as
                # broken, because the rows are
                # ordered by this score while
                # `score` stays on the cosine
                # scale.
                "rerank_score": (
                    round(
                        result[
                            "rerank_score"
                        ],
                        4,
                    )
                    if "rerank_score" in result
                    else None
                ),
                "chunk_id": result[
                    "chunk_id"
                ],
                "policy_id": metadata.get(
                    "policy_id",
                    "",
                ),
                "section": metadata.get(
                    "section",
                    "",
                ),
                "preview": result["text"][
                    :PREVIEW_LENGTH
                ],
            }
        )

    return described


def evaluate_strategy(
    strategy: str,
    questions: list[dict],
    rerank: bool = False,
) -> dict:

    retriever = Retriever(
        strategy,
        rerank=rerank,
    )

    records = []

    for question in questions:

        retrieved = retriever.retrieve(
            question["question"],
            top_k=CANDIDATE_K,
        )

        targets = expected_targets(
            question
        )

        matched_ranks = match_ranks(
            retrieved,
            targets,
        )

        best_rank = (
            min(matched_ranks.values())
            if matched_ranks
            else None
        )

        records.append(
            {
                "question_id": question["id"],
                "question": question[
                    "question"
                ],
                "expected": question[
                    "expected"
                ],
                "expected_total": len(
                    targets
                ),
                "matched_ranks": matched_ranks,
                "best_rank": best_rank,
                "hit_at_k": bool(
                    ranks_within_k(
                        {
                            "matched_ranks": matched_ranks
                        },
                        SCORE_K,
                    )
                ),
                "retrieved": describe_retrieved(
                    retrieved
                ),
            }
        )

    return {
        "strategy": strategy,
        "rerank": rerank,
        "indexed_chunks": retriever.vector_store.count(),
        "summary": summarise(records),
        "records": records,
    }


def summarise(
    records: list[dict],
) -> dict:

    summary = {
        "questions": len(records),
        "mrr": round(
            mrr(records),
            4,
        ),
    }

    for k in REPORT_KS:

        summary[f"hit_rate_at_{k}"] = round(
            hit_rate_at_k(
                records,
                k,
            ),
            4,
        )

        summary[f"recall_at_{k}"] = round(
            recall_at_k(
                records,
                k,
            ),
            4,
        )

    return summary


def compare(
    runs: dict,
) -> dict:
    """
    The before-and-after table, plus which
    questions the change moved.
    """

    baseline = runs[BASELINE_ARM]

    changed = runs[CHANGED_ARM]

    before = {
        record["question_id"]: record
        for record in baseline["records"]
    }

    movements = []

    for record in changed["records"]:

        previous = before[
            record["question_id"]
        ]

        if record["hit_at_k"] and not previous[
            "hit_at_k"
        ]:
            outcome = "fixed"

        elif previous[
            "hit_at_k"
        ] and not record["hit_at_k"]:
            outcome = "newly_broken"

        elif record["hit_at_k"]:
            outcome = "already_passing"

        else:
            outcome = "still_broken"

        movements.append(
            {
                "question_id": record[
                    "question_id"
                ],
                "outcome": outcome,
                "rank_before": previous[
                    "best_rank"
                ],
                "rank_after": record[
                    "best_rank"
                ],
            }
        )

    return {
        "baseline_arm": BASELINE_ARM,
        "changed_arm": CHANGED_ARM,
        "before": baseline["summary"],
        "after": changed["summary"],
        "movements": movements,
    }


def main():

    questions = load_questions()

    runs = {}

    for arm in ARMS:

        run = evaluate_strategy(
            arm["strategy"],
            questions,
            rerank=arm["rerank"],
        )

        runs[arm["name"]] = run

        summary = run["summary"]

        print(
            f"{arm['name']}: "
            f"hit_rate@{SCORE_K}="
            f"{summary[f'hit_rate_at_{SCORE_K}']} "
            f"hit_rate@1="
            f"{summary['hit_rate_at_1']} "
            f"mrr={summary['mrr']} "
            f"({run['indexed_chunks']} chunks)"
        )

    report = {
        "status": "measured",
        "config": {
            "embedding_model": EMBEDDING_MODEL,
            "candidate_k": CANDIDATE_K,
            "score_k": SCORE_K,
            "authoritative_strategy": (
                AUTHORITATIVE_STRATEGY
            ),
            "rerank_pool_multiplier": (
                RERANK_POOL_MULTIPLIER
            ),
            "rerank_model": RERANK_MODEL,
        },
        "comparison": compare(runs),
        "notes": [
            "hit_rate/recall/mrr are scored on the "
            "(policy_id, section) pair.",
            "recall_at_k equals hit_rate_at_k while "
            "every question has one expected target.",
            "The basic strategy's section labels are "
            "unreliable: extract_section reads the "
            "first number in a blind character window, "
            "so its scores measure label noise, not "
            "retrieval. structure_aware is the "
            "authoritative arm.",
        ],
        "runs": runs,
    }

    with open(
        "evaluation/retrieval_results.json",
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            report,
            file,
            indent=2,
        )


if __name__ == "__main__":
    main()
