from app.services import reranker


class StubCrossEncoder:
    """
    Returns a score per pair from a lookup, so the
    ranking logic is testable without loading the
    real cross-encoder.
    """

    def __init__(
        self,
        scores: dict,
    ):

        self.scores = scores

    def predict(
        self,
        pairs: list[tuple],
    ) -> list[float]:

        return [
            self.scores[text]
            for _, text in pairs
        ]


def chunk(
    text: str,
    score: float,
) -> dict:

    return {
        "chunk_id": text,
        "text": text,
        "score": score,
        "metadata": {},
    }


def use_stub(
    monkeypatch,
    scores: dict,
):

    monkeypatch.setattr(
        reranker,
        "get_reranker",
        lambda: StubCrossEncoder(
            scores
        ),
    )


def test_empty_results_need_no_model():
    """
    Returns before loading the cross-encoder,
    which is what keeps this test cheap.
    """

    assert (
        reranker.rerank_results(
            "any question",
            [],
        )
        == []
    )


def test_the_better_chunk_moves_to_the_top(
    monkeypatch,
):

    use_stub(
        monkeypatch,
        {
            "weak": 0.1,
            "strong": 0.9,
        },
    )

    results = reranker.rerank_results(
        "question",
        [
            chunk("weak", 0.80),
            chunk("strong", 0.79),
        ],
    )

    assert results[0]["text"] == "strong"


def test_top_k_is_respected(
    monkeypatch,
):

    use_stub(
        monkeypatch,
        {
            "a": 0.3,
            "b": 0.2,
            "c": 0.1,
        },
    )

    results = reranker.rerank_results(
        "question",
        [
            chunk("a", 0.5),
            chunk("b", 0.5),
            chunk("c", 0.5),
        ],
        top_k=2,
    )

    assert len(results) == 2


def test_the_vector_score_is_preserved(
    monkeypatch,
):
    """
    has_good_match thresholds on the cosine
    scale, so the original score must survive.
    """

    use_stub(
        monkeypatch,
        {"only": 4.2},
    )

    result = reranker.rerank_results(
        "question",
        [chunk("only", 0.61)],
    )[0]

    assert result["vector_score"] == 0.61
    assert result["rerank_score"] == 4.2
