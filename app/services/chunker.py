import re
from typing import Any


def split_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> list[str]:
    """
    Basic character-based chunking.
    """

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    if not text:
        return []

    if chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap must be smaller than chunk_size"
        )

    chunks = []

    start = 0
    text_length = len(text)

    while start < text_length:

        end = min(
            start + chunk_size,
            text_length,
        )

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        start = end - chunk_overlap

    return chunks


def basic_chunk_documents(
    pages: list[dict],
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> list[dict]:
    """
    Basic chunking strategy.

    This intentionally does not understand policy structure.
    """

    chunks = []

    for page in pages:

        text_chunks = split_text(
            page["text"],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        for index, text in enumerate(text_chunks):

            chunks.append(
                {
                    "text": text,
                    "source_file": page["source_file"],
                    "page_number": page["page_number"],
                    "chunk_index": index,
                    "chunking_strategy": "basic",
                }
            )

    return chunks


SECTION_PATTERN = re.compile(
    r"(?im)"
    r"(?=^"
    r"(?:section\s+)?"
    r"\d+(?:\.\d+)*"
    r"(?:\s+|[:\-])"
    r")"
)


def structure_aware_chunk_text(
    text: str,
) -> list[str]:
    """
    Structure-aware chunking.

    Attempts to keep numbered policy sections together.
    """

    text = text.replace(
        "\r\n",
        "\n",
    )

    text = text.strip()

    if not text:
        return []

    matches = list(
        SECTION_PATTERN.finditer(text)
    )

    if not matches:
        return split_text(
            text,
            chunk_size=1000,
            chunk_overlap=150,
        )

    chunks = []

    # Content before first section.
    first_start = matches[0].start()

    if first_start > 0:
        prefix = text[:first_start].strip()

        if prefix:
            chunks.append(prefix)

    for index, match in enumerate(matches):

        start = match.start()

        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            end = len(text)

        section_text = text[start:end].strip()

        if section_text:
            chunks.append(section_text)

    return chunks


def structure_aware_chunk_documents(
    pages: list[dict],
) -> list[dict]:
    """
    Structure-aware chunking strategy.
    """

    chunks = []

    for page in pages:

        text_chunks = structure_aware_chunk_text(
            page["text"]
        )

        for index, text in enumerate(text_chunks):

            chunks.append(
                {
                    "text": text,
                    "source_file": page["source_file"],
                    "page_number": page["page_number"],
                    "chunk_index": index,
                    "chunking_strategy": "structure_aware",
                }
            )

    return chunks


def extract_policy_id(
    source_file: str,
) -> str:
    """
    Example:

    HR-207.pdf -> HR-207
    """

    filename = source_file.rsplit(
        ".",
        1,
    )[0]

    return filename


def extract_section(
    text: str,
) -> str:
    """
    Attempts to find a section number.

    Example:

    4.2 Carry Over Rules

    returns:

    4.2
    """

    match = re.search(
        r"(?im)"
        r"(?:section\s+)?"
        r"(\d+(?:\.\d+)*)"
        r"(?:\s+|[:\-])",
        text,
    )

    if match:
        return match.group(1)

    return "unknown"


def create_metadata(
    chunk: dict[str, Any],
) -> dict[str, Any]:

    source_file = chunk["source_file"]

    policy_id = extract_policy_id(
        source_file
    )

    section = extract_section(
        chunk["text"]
    )

    # These values are placeholders until
    # you extract them from your actual documents.
    region = chunk.get(
        "region",
        "unknown",
    )

    effective_date = chunk.get(
        "effective_date",
        "unknown",
    )

    return {
        "source_file": source_file,
        "policy_id": policy_id,
        "section": section,
        "page_number": chunk.get(
            "page_number",
            0,
        ),
        "region": region,
        "effective_date": effective_date,
        "chunking_strategy": chunk[
            "chunking_strategy"
        ],
    }