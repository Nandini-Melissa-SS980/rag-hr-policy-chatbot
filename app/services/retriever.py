from app.services.vector_store import VectorStore


class Retriever:

    def __init__(
        self,
        strategy: str = "structure_aware",
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

        return self.vector_store.search(
            query=question,
            top_k=top_k,
            where=where,
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