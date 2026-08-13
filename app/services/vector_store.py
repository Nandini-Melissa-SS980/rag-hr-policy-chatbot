import os
import uuid

import chromadb

from app.config import CHROMA_PATH
from app.services.embeddings import (
    embed_texts,
)


class VectorStore:

    def __init__(
        self,
        collection_name: str,
    ):

        os.makedirs(
            CHROMA_PATH,
            exist_ok=True,
        )

        self.client = chromadb.PersistentClient(
            path=CHROMA_PATH
        )

        self.collection = (
            self.client.get_or_create_collection(
                name=collection_name,
                metadata={
                    "hnsw:space": "cosine"
                },
            )
        )

    def add_documents(
        self,
        chunks: list[dict],
    ) -> int:

        if not chunks:
            return 0

        texts = [
            chunk["text"]
            for chunk in chunks
        ]

        embeddings = embed_texts(
            texts
        )

        ids = []

        metadatas = []

        documents = []

        for index, chunk in enumerate(
            chunks
        ):

            metadata = chunk["metadata"]

            chunk_id = (
                f"{metadata['policy_id']}-"
                f"{metadata['section']}-"
                f"{metadata['chunking_strategy']}-"
                f"{index}-"
                f"{uuid.uuid4().hex[:8]}"
            )

            ids.append(chunk_id)

            metadatas.append(
                {
                    **metadata,
                    "chunk_id": chunk_id,
                }
            )

            documents.append(
                chunk["text"]
            )

        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        return len(chunks)

    def search(
        self,
        query: str,
        top_k: int = 5,
        where: dict | None = None,
    ) -> list[dict]:

        query_embedding = embed_texts(
            [query]
        )[0]

        kwargs = {
            "query_embeddings": [
                query_embedding
            ],
            "n_results": top_k,
            "include": [
                "documents",
                "metadatas",
                "distances",
            ],
        }

        if where:
            kwargs["where"] = where

        result = self.collection.query(
            **kwargs
        )

        documents = result.get(
            "documents",
            [[]],
        )[0]

        metadatas = result.get(
            "metadatas",
            [[]],
        )[0]

        distances = result.get(
            "distances",
            [[]],
        )[0]

        results = []

        for document, metadata, distance in zip(
            documents,
            metadatas,
            distances,
        ):

            score = 1 - distance

            results.append(
                {
                    "chunk_id": metadata.get(
                        "chunk_id",
                        "",
                    ),
                    "text": document,
                    "score": float(score),
                    "metadata": metadata,
                }
            )

        return results

    def count(self) -> int:
        return self.collection.count()