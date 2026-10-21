"""
The desk's retriever.

A thin wrapper over `VectorStore` that accepts a `where`
clause, because the desk's correctness depends on filtering by
entity and the Week-4 `Retriever` takes a `region` string and
is pinned to its own two collections.

Deliberately NOT a change to `app/services/retriever.py`. The
retrieval numbers in evaluation/results.md were measured
against that class and that index; widening its signature for
the capstone would make a Week-4 number and a Week-12 number
describe different code with the same name.
"""

from app.config import DESK_COLLECTION
from app.services.vector_store import VectorStore


class DeskRetriever:

    def __init__(
        self,
        collection: str = DESK_COLLECTION,
    ):

        self.collection = collection

        self.vector_store = VectorStore(collection)

    def retrieve(
        self,
        question: str,
        top_k: int = 6,
        where: dict | None = None,
    ) -> list[dict]:

        return self.vector_store.search(
            query=question,
            top_k=top_k,
            where=where,
        )

    def all_metadata(self) -> list[dict]:

        return self.vector_store.all_metadata()

    @staticmethod
    def has_good_match(
        results: list[dict],
        threshold: float = 0.45,
    ) -> bool:

        return bool(
            results
            and results[0]["score"] >= threshold
        )
