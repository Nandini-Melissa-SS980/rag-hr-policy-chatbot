"""
Retrieval metrics.

A record is one evaluated question:

    {
        "matched_ranks": {"HR-207|4.2": 2},
        "expected_total": 1,
    }

`matched_ranks` maps an expected target to the
best (lowest) one-based rank it was retrieved
at. Targets never retrieved are absent.
"""


def ranks_within_k(
    record: dict,
    k: int,
) -> list[int]:
    """
    Ranks of the expected targets that were
    retrieved inside the top k.
    """

    return [
        rank
        for rank in record[
            "matched_ranks"
        ].values()
        if rank <= k
    ]


def hit_rate_at_k(
    records: list[dict],
    k: int,
) -> float:
    """
    Share of questions with at least one
    expected target in the top k.
    """

    if not records:
        return 0.0

    hits = sum(
        1
        for record in records
        if ranks_within_k(
            record,
            k,
        )
    )

    return hits / len(records)


def recall_at_k(
    records: list[dict],
    k: int,
) -> float:
    """
    Mean fraction of a question's expected
    targets found in the top k.

    Identical to hit_rate_at_k while every
    question has exactly one expected target.
    """

    if not records:
        return 0.0

    total = 0.0

    for record in records:

        expected_total = record[
            "expected_total"
        ]

        if not expected_total:
            continue

        found = len(
            ranks_within_k(
                record,
                k,
            )
        )

        total += (
            min(
                found,
                expected_total,
            )
            / expected_total
        )

    return total / len(records)


def mrr(
    records: list[dict],
    k: int | None = None,
) -> float:
    """
    Mean reciprocal rank of the first expected
    target. Questions with no match score zero.
    """

    if not records:
        return 0.0

    total = 0.0

    for record in records:

        ranks = list(
            record[
                "matched_ranks"
            ].values()
        )

        if k is not None:
            ranks = [
                rank
                for rank in ranks
                if rank <= k
            ]

        if not ranks:
            continue

        total += 1 / min(ranks)

    return total / len(records)
