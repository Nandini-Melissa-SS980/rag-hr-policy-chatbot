from evaluation.metrics import (
    hit_rate_at_k,
    mrr,
    ranks_within_k,
    recall_at_k,
)


def record(
    *ranks: int,
    expected_total: int = 1,
) -> dict:

    return {
        "matched_ranks": {
            f"HR-20{index}|4.2": rank
            for index, rank in enumerate(
                ranks
            )
        },
        "expected_total": expected_total,
    }


def test_ranks_within_k_excludes_deeper_ranks():

    assert ranks_within_k(
        record(2, 7),
        3,
    ) == [2]


def test_hit_rate_counts_a_hit_at_rank_three():

    assert (
        hit_rate_at_k(
            [record(3)],
            3,
        )
        == 1.0
    )


def test_hit_rate_misses_a_hit_at_rank_four():

    assert (
        hit_rate_at_k(
            [record(4)],
            3,
        )
        == 0.0
    )


def test_hit_rate_averages_over_questions():

    records = [
        record(1),
        record(9),
    ]

    assert (
        hit_rate_at_k(
            records,
            3,
        )
        == 0.5
    )


def test_a_question_with_no_match_scores_zero():

    assert (
        hit_rate_at_k(
            [record()],
            3,
        )
        == 0.0
    )

    assert (
        mrr([record()])
        == 0.0
    )


def test_mrr_is_half_when_expected_is_second():

    assert (
        mrr([record(2)])
        == 0.5
    )


def test_mrr_uses_the_best_rank():

    assert (
        mrr([record(5, 2)])
        == 0.5
    )


def test_mrr_can_ignore_ranks_beyond_k():

    assert (
        mrr(
            [record(4)],
            k=3,
        )
        == 0.0
    )


def test_recall_is_partial_when_one_target_is_missed():

    records = [
        record(
            1,
            8,
            expected_total=2,
        )
    ]

    assert (
        recall_at_k(
            records,
            3,
        )
        == 0.5
    )


def test_recall_matches_hit_rate_for_one_target():
    """
    Documents why the report carries both:
    they only diverge once a question has more
    than one expected target.
    """

    records = [
        record(1),
        record(9),
    ]

    assert recall_at_k(
        records,
        3,
    ) == hit_rate_at_k(
        records,
        3,
    )


def test_empty_records_score_zero():

    assert hit_rate_at_k([], 3) == 0.0
    assert recall_at_k([], 3) == 0.0
    assert mrr([]) == 0.0
