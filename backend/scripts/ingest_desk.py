"""
Build the Week-12 index.

    python -m scripts.ingest_desk

One collection holding three kinds of document:

    versioned/  the leave policy in its 2024 and 2025 editions
    annexes/    the India and UK entity annexes
    matrices/   the grade-band matrix

Every chunk carries version, effective_date, superseded_on and
entity as declared metadata, lifted from each document's front
matter. That is the whole point: the desk filters on those
fields, and a filter can only enforce what is declared.

The Week-4 collections are left alone. The retrieval numbers
in evaluation/results.md were measured against them and stay
reproducible.
"""

from app.config import (
    ANNEXES_DIR,
    DESK_COLLECTION,
    MATRICES_DIR,
    VERSIONED_DIR,
)
from app.services.markdown_loader import (
    load_markdown_directories,
)
from app.services.vector_store import VectorStore


def main():

    chunks = load_markdown_directories(
        [
            VERSIONED_DIR,
            ANNEXES_DIR,
            MATRICES_DIR,
        ]
    )

    if not chunks:

        raise SystemExit(
            "No documents found. Expected .md files "
            f"under {VERSIONED_DIR}, {ANNEXES_DIR} "
            f"or {MATRICES_DIR}."
        )

    prepared = []

    for chunk in chunks:

        prepared.append(
            {
                "text": chunk["text"],
                "metadata": {
                    "source_file": chunk[
                        "source_file"
                    ],
                    "policy_id": chunk[
                        "policy_id"
                    ],
                    "section": chunk["section"],
                    "heading": chunk["heading"],
                    "title": chunk["title"],
                    "page_number": 0,
                    "chunking_strategy": (
                        "front_matter"
                    ),
                    # The fields the desk filters on.
                    "version": chunk["version"],
                    "effective_date": chunk[
                        "effective_date"
                    ],
                    "superseded_on": chunk[
                        "superseded_on"
                    ],
                    "entity": chunk["entity"],
                    "overrides": chunk["overrides"],
                },
            }
        )

    store = VectorStore(DESK_COLLECTION)

    # Rebuilt rather than appended: a half-updated index that
    # holds two copies of one clause is worse than no index,
    # because the duplicate ranks and the citation is
    # ambiguous.
    try:
        store.client.delete_collection(
            DESK_COLLECTION
        )

    except Exception:
        pass

    store = VectorStore(DESK_COLLECTION)

    added = store.add_documents(prepared)

    print(
        f"Indexed {added} chunks into "
        f"'{DESK_COLLECTION}'."
    )

    entities: dict = {}

    versions: dict = {}

    for chunk in prepared:

        entity = chunk["metadata"]["entity"]

        entities[entity] = (
            entities.get(entity, 0) + 1
        )

        key = (
            f"{chunk['metadata']['policy_id']}"
            f" {chunk['metadata']['version']}"
        )

        versions[key] = versions.get(key, 0) + 1

    print("\nby entity:")

    for entity in sorted(entities):
        print(f"  {entity:<8} {entities[entity]}")

    print("\nby policy and version:")

    for key in sorted(versions):
        print(f"  {key:<22} {versions[key]}")


if __name__ == "__main__":
    main()
