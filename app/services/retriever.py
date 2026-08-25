from app.services.vector_store import VectorStore


# How many candidates the reranker sees per
# requested result. A cross-encoder is slow but
# accurate, so it is affordable to widen the
# pool it reorders.
RERANK_POOL_MULTIPLIER = 3


class Retriever:

    def __init__(
        self,
        strategy: str = "structure_aware",
        rerank: bool = False,
    ):

        if strategy == "basic":

            collection = (
                "hr_policy_basic"
            )

        elif strategy == "structure_aware":

            collection = (
                "hr_policy_structure_aware"
            )

        else:

            raise ValueError(
                "Invalid strategy"
            )

        self.strategy = strategy

        self.rerank = rerank

        self.vector_store = VectorStore(
            collection
        )

    def retrieve(
        self,
        question: str,
        top_k: int = 5,
        region: str | None = None,
    ) -> list[dict]:

        where = None

        if region:

            where = {
                "region": region
            }

        candidate_k = top_k

        if self.rerank:

            candidate_k = (
                top_k
                * RERANK_POOL_MULTIPLIER
            )

        results = self.vector_store.search(
            query=question,
            top_k=candidate_k,
            where=where,
        )

        if not self.rerank:
            return results

        # Imported lazily so the baseline path
        # never loads the cross-encoder.
        from app.services.reranker import (
            rerank_results,
        )

        return rerank_results(
            question,
            results,
            top_k=top_k,
        )

    @staticmethod
    def has_good_match(
        results: list[dict],
        threshold: float = 0.45,
    ) -> bool:

        return bool(
            results
            and results[0]["score"]
            >= threshold
        )