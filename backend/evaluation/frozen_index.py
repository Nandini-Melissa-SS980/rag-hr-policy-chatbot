"""
The policy index, read without the embedding model.

The trajectory eval needs two things from the index:

  - the (policy_id, section) pairs that really exist,
    so a citation can be checked against them
  - passages for search_handbook, so the tool under
    evaluation is the real tool and not a stub

On a machine with the embedding stack installed both
come from the real `Retriever`. This module is the
fallback for a machine without it: it reads the
chunks straight out of the Chroma sqlite file and
ranks them by word overlap.

Ranking quality is a Week-4 question and is measured
in results.md. What the trajectory eval reads from
this tool is the call, its arguments, and the
sections it hands back - and those are the real ones
either way, because the text and the metadata come
out of the same index the app serves from. Which
source was used is recorded in the results JSON, so
a number produced under the fallback is never
mistaken for one produced under the real retriever.
"""

import os
import re
import sqlite3

from app.config import BASE_DIR, CHROMA_PATH


COLLECTION = "hr_policy_structure_aware"

SQLITE_NAME = "chroma.sqlite3"

WORD = re.compile(r"[a-z0-9]+")

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "can",
    "do",
    "does",
    "for",
    "get",
    "give",
    "how",
    "i",
    "in",
    "is",
    "many",
    "much",
    "must",
    "my",
    "of",
    "on",
    "or",
    "the",
    "they",
    "to",
    "what",
    "which",
}


def sqlite_path() -> str:

    if os.path.isabs(CHROMA_PATH):
        base = CHROMA_PATH

    else:
        base = os.path.join(
            BASE_DIR,
            CHROMA_PATH.lstrip("./"),
        )

    return os.path.join(
        base,
        SQLITE_NAME,
    )


def read_chunks(
    collection: str = COLLECTION,
) -> list[dict]:
    """
    Every chunk in one collection, as
    {policy_id, section, text}.

    Chroma keeps documents and metadata in the same
    sqlite file it keeps its bookkeeping in, one row
    per (chunk, metadata key). This reassembles them
    without going through the client, because the
    client needs its native extension and the
    extension is not always loadable.
    """

    path = sqlite_path()

    if not os.path.exists(path):
        return []

    connection = sqlite3.connect(path)

    try:

        segment = connection.execute(
            """
            select segments.id
            from segments
            join collections
              on collections.id
               = segments.collection
            where collections.name = ?
              and segments.scope = 'METADATA'
            """,
            (collection,),
        ).fetchone()

        if segment is None:
            return []

        rows = connection.execute(
            """
            select
              embeddings.id,
              embedding_metadata.key,
              coalesce(
                embedding_metadata.string_value,
                cast(
                  embedding_metadata.int_value
                  as text
                )
              )
            from embeddings
            join embedding_metadata
              on embedding_metadata.id
               = embeddings.id
            where embeddings.segment_id = ?
            """,
            (segment[0],),
        ).fetchall()

    finally:
        connection.close()

    assembled: dict = {}

    for chunk_id, key, value in rows:

        assembled.setdefault(
            chunk_id,
            {},
        )[key] = value

    chunks = []

    for fields in assembled.values():

        chunks.append(
            {
                "policy_id": fields.get(
                    "policy_id",
                    "",
                ),
                "section": fields.get(
                    "section",
                    "",
                ),
                "text": fields.get(
                    "chroma:document",
                    "",
                ),
            }
        )

    chunks.sort(
        key=lambda chunk: (
            chunk["policy_id"],
            chunk["section"],
        )
    )

    return chunks


def words(text: str) -> set[str]:

    return {
        word
        for word in WORD.findall(
            (text or "").lower()
        )
        if word not in STOPWORDS
    }


class LexicalHandbook:
    """
    The same interface as `Retriever`, ranked by how
    many of the query's words a chunk contains.

    Stands in for the bi-encoder on a machine without
    it. It is not as good, and it is not pretending
    to be: it exists so that search_handbook returns
    real policy text with real section numbers when
    the trajectory eval calls it.
    """

    source = "frozen_lexical"

    def __init__(
        self,
        collection: str = COLLECTION,
    ):

        self.chunks = read_chunks(collection)

        self.indexed = [
            (chunk, words(chunk["text"]))
            for chunk in self.chunks
        ]

    def retrieve(
        self,
        question: str,
        top_k: int = 3,
        region: str | None = None,
    ) -> list[dict]:

        asked = words(question)

        if not asked:
            return []

        scored = []

        for chunk, chunk_words in self.indexed:

            overlap = len(
                asked & chunk_words
            )

            if not overlap:
                continue

            scored.append(
                (
                    overlap / len(asked),
                    chunk,
                )
            )

        scored.sort(
            key=lambda pair: (
                -pair[0],
                pair[1]["policy_id"],
                pair[1]["section"],
            )
        )

        return [
            {
                "chunk_id": (
                    f"{chunk['policy_id']}-"
                    f"{chunk['section']}"
                ),
                "text": chunk["text"],
                "score": round(score, 4),
                "metadata": {
                    "policy_id": chunk[
                        "policy_id"
                    ],
                    "section": chunk["section"],
                },
            }
            for score, chunk in scored[:top_k]
        ]


def build_handbook() -> tuple:
    """
    The real retriever if it will load, the frozen
    one if it will not.

    Returns (retriever_or_None, source_name). None
    means "use the app's own retriever", which is
    what `build_toolset` does when no retriever is
    injected.
    """

    try:

        from app.services.retriever import (
            Retriever,
        )

        retriever = Retriever(
            "structure_aware"
        )

        # Cheap proof it can actually serve, not
        # just import: a retriever that cannot embed
        # raises here rather than mid-eval.
        retriever.retrieve(
            "annual leave",
            top_k=1,
        )

        return retriever, "live_retriever"

    except Exception:

        return LexicalHandbook(), "frozen_lexical"


def valid_sections(
    collection: str = COLLECTION,
) -> set:
    """
    Every (policy_id, section) pair in the index.

    A citation to anything outside this set is
    fiction, however well formed it looks.
    """

    return {
        (
            chunk["policy_id"],
            chunk["section"],
        )
        for chunk in read_chunks(collection)
    }
