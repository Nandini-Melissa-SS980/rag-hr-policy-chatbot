import os

from app.config import ADDENDA_DIR
from app.services.chunker import (
    basic_chunk_documents,
    create_metadata,
    structure_aware_chunk_documents,
)
from app.services.document_loader import (
    load_directory,
)
from app.services.vector_store import (
    VectorStore,
)


def prepare_chunks(
    pages: list[dict],
    strategy: str,
) -> list[dict]:

    if strategy == "basic":

        chunks = basic_chunk_documents(
            pages,
            chunk_size=1000,
            chunk_overlap=150,
        )

    else:

        chunks = (
            structure_aware_chunk_documents(
                pages
            )
        )

    prepared = []

    for chunk in chunks:

        metadata = create_metadata(
            chunk
        )

        prepared.append(
            {
                "text": chunk["text"],
                "metadata": metadata,
            }
        )

    return prepared


def main():

    if not os.path.exists(
        ADDENDA_DIR
    ):
        raise RuntimeError(
            "Addenda directory does not exist."
        )

    pages = load_directory(
        ADDENDA_DIR
    )

    print(
        f"Loaded {len(pages)} pages."
    )

    # -----------------------------
    # BASIC
    # -----------------------------

    basic_store = VectorStore(
        "hr_policy_basic"
    )

    basic_chunks = prepare_chunks(
        pages,
        "basic",
    )

    basic_store.add_documents(
        basic_chunks
    )

    print(
        f"Basic strategy: "
        f"{len(basic_chunks)} chunks"
    )

    # -----------------------------
    # STRUCTURE AWARE
    # -----------------------------

    structure_store = VectorStore(
        "hr_policy_structure_aware"
    )

    structure_chunks = prepare_chunks(
        pages,
        "structure_aware",
    )

    structure_store.add_documents(
        structure_chunks
    )

    print(
        "Structure-aware strategy: "
        f"{len(structure_chunks)} chunks"
    )

    print("Ingestion complete.")


if __name__ == "__main__":
    main()