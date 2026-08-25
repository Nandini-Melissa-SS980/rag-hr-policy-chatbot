from functools import lru_cache

from sentence_transformers import CrossEncoder

from app.config import RERANK_MODEL


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoder:
    """
    Load the cross-encoder once.
    """

    return CrossEncoder(
        RERANK_MODEL
    )


def rerank_results(
    question: str,
    results: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """
    Reorder retrieved chunks with a cross-encoder.

    The embedding model scores the question and a
    chunk separately, so it never compares them
    directly. A cross-encoder reads both together
    and scores the pair, which is slower but far
    better at ranking.

    The original vector score is preserved as
    `vector_score`, because `has_good_match`
    thresholds on the cosine scale and rerank
    scores are unbounded logits.
    """

    if not results:
        return []

    model = get_reranker()

    pairs = [
        (
            question,
            result["text"],
        )
        for result in results
    ]

    scores = model.predict(pairs)

    reranked = []

    for result, score in zip(
        results,
        scores,
    ):

        reranked.append(
            {
                **result,
                "vector_score": result[
                    "score"
                ],
                "rerank_score": float(
                    score
                ),
            }
        )

    reranked.sort(
        key=lambda result: result[
            "rerank_score"
        ],
        reverse=True,
    )

    return reranked[:top_k]
