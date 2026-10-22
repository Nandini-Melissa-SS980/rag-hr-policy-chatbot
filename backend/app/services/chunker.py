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

        if not section_text:
            continue

        # A parent heading followed immediately by its first
        # subsection produces a chunk holding only the
        # heading - "2 Working Hours", 15 characters, no
        # body. Eight of sixty-five chunks were these.
        #
        # They are worse than useless: they carry the
        # section's own words so they rank highly, then
        # answer nothing. One topped the results for "how
        # many days of annual leave do I get" at 0.833.
        #
        # Dropped rather than merged into the next section:
        # the subsection that follows already repeats the
        # parent's topic in its own heading, so nothing is
        # lost, and merging would blur the boundary a
        # citation points at.
        if is_heading_only(section_text):
            continue

        chunks.append(section_text)

    return chunks


# A section whose body is shorter than this is a heading, not
# a clause.
#
# Measured, not guessed. Across the six policies every bare
# heading has a body of exactly 0 characters, and the
# shortest real clause has 100. There is no overlap at all,
# so this sits just above zero rather than in the middle of
# a gap that does not exist - a higher threshold would start
# discarding short but genuine clauses, which is a silent
# loss of policy.
MIN_SECTION_BODY = 16


def is_heading_only(section_text: str) -> bool:
    """
    Whether this chunk is a bare heading with no body.

    Measured on the text after the heading line, because the
    heading itself can be long enough to pass a naive length
    check while saying nothing.
    """

    lines = section_text.strip().split("\n", 1)

    body = lines[1].strip() if len(lines) > 1 else ""

    return len(body) < MIN_SECTION_BODY


def structure_aware_chunk_documents(
    pages: list[dict],
) -> list[dict]:
    """
    Structure-aware chunking strategy.
    """

    chunks = []

    # Joined per document before chunking, not per page.
    #
    # Chunking page by page cuts any clause that spans a page
    # break. HR-201 section 3 produced a chunk reading only
    # "the first day back at work." - the tail of a sentence
    # whose head was on the previous page, indexed as though
    # it were a clause.
    #
    # A section is a unit of the document, not of the page it
    # happens to land on, so the document is reassembled
    # first and the section pattern decides the boundaries.
    for source_file, document in group_by_document(
        pages
    ).items():

        text_chunks = structure_aware_chunk_text(
            document["text"]
        )

        for index, text in enumerate(text_chunks):

            chunks.append(
                {
                    "text": text,
                    "source_file": source_file,
                    # The page the section STARTS on, found
                    # by locating its offset in the joined
                    # text. A section spanning two pages is
                    # cited by where it begins, which is how
                    # someone reading the PDF would cite it.
                    "page_number": page_of_offset(
                        document,
                        document["text"].find(text),
                    ),
                    "chunk_index": index,
                    "chunking_strategy": "structure_aware",
                }
            )

    return chunks


def group_by_document(
    pages: list[dict],
) -> dict:
    """
    Pages joined back into whole documents.

    Keeps each page's start offset so a chunk can still be
    attributed to the page it begins on.
    """

    documents: dict = {}

    for page in pages:

        document = documents.setdefault(
            page["source_file"],
            {"text": "", "offsets": []},
        )

        document["offsets"].append(
            (
                len(document["text"]),
                page["page_number"],
            )
        )

        # A newline, so a heading at the top of a page is
        # still recognised as starting a line.
        if document["text"]:
            document["text"] += "\n"

        document["text"] += page["text"]

    return documents


def page_of_offset(
    document: dict,
    offset: int,
) -> int:
    """
    Which page a character offset falls on.
    """

    if offset < 0:
        return document["offsets"][0][1]

    page_number = document["offsets"][0][1]

    for start, number in document["offsets"]:

        if start > offset:
            break

        page_number = number

    return page_number


def extract_policy_id(
    source_file: str,
) -> str:
    """
    Example:

    HR-206.pdf -> HR-206
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