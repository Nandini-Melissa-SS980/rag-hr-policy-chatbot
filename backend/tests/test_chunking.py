import pytest

from app.services.chunker import (
    basic_chunk_documents,
    create_metadata,
    extract_policy_id,
    extract_section,
    split_text,
    structure_aware_chunk_text,
)


PAGE = {
    "text": (
        "4.1 Entitlement\n"
        "Employees receive twenty-five days.\n"
        "4.2 Carry Over\n"
        "Up to five days may be carried over."
    ),
    "source_file": "HR-202.pdf",
    "page_number": 1,
}


def test_split_text_respects_chunk_size():

    chunks = split_text(
        "word " * 500,
        chunk_size=100,
        chunk_overlap=10,
    )

    assert len(chunks) > 1
    assert all(
        len(chunk) <= 100
        for chunk in chunks
    )


def test_split_text_rejects_bad_overlap():

    with pytest.raises(ValueError):
        split_text(
            "text",
            chunk_size=100,
            chunk_overlap=100,
        )


def test_split_text_handles_empty_text():

    assert split_text("   ") == []


def test_structure_aware_splits_on_sections():

    chunks = structure_aware_chunk_text(
        PAGE["text"]
    )

    assert len(chunks) == 2
    assert chunks[0].startswith("4.1")
    assert chunks[1].startswith("4.2")


def test_section_number_stays_with_its_clause():

    chunks = structure_aware_chunk_text(
        PAGE["text"]
    )

    carry_over = chunks[1]

    assert "4.2" in carry_over
    assert "five days" in carry_over


def test_basic_chunking_tags_the_strategy():

    chunks = basic_chunk_documents(
        [PAGE]
    )

    assert chunks
    assert all(
        chunk["chunking_strategy"] == "basic"
        for chunk in chunks
    )


def test_extract_policy_id():

    assert (
        extract_policy_id("HR-206.pdf")
        == "HR-206"
    )


def test_extract_section():

    assert (
        extract_section("4.2 Carry Over")
        == "4.2"
    )

    assert (
        extract_section("No number here")
        == "unknown"
    )


def test_extract_section_picks_up_the_policy_number():
    """
    Documents the section bug: the pattern matches
    any number, so a chunk opening with the policy
    header is labelled '201' instead of a section.

    This is why the basic strategy scores 0/8 in
    the retrieval report — its labels rarely
    describe the text they are attached to.
    """

    assert (
        extract_section(
            "HR-201 Attendance Policy ID: HR-201"
        )
        == "201"
    )


def test_metadata_has_the_required_fields():

    chunk = basic_chunk_documents(
        [PAGE]
    )[0]

    metadata = create_metadata(chunk)

    assert metadata["source_file"] == "HR-202.pdf"
    assert metadata["policy_id"] == "HR-202"
    assert "region" in metadata
    assert "effective_date" in metadata


# ---------------- heading-only chunks --------------


def test_a_bare_heading_is_not_indexed():
    """
    A parent heading followed straight by its first
    subsection used to produce a chunk holding only the
    heading - "2 Working Hours", 15 characters, no body.

    Eight of sixty-five chunks were these, and they are
    worse than useless: they carry the section's own words
    so they rank highly, then answer nothing. One topped the
    results for "how many days of annual leave do I get" at
    0.833.
    """

    chunks = structure_aware_chunk_text(
        "2 Working Hours\n"
        "2.1 Standard Hours\n"
        "The standard working week is thirty-seven "
        "and a half hours, Monday to Friday.\n"
    )

    assert not any(
        chunk.strip() == "2 Working Hours"
        for chunk in chunks
    ), "the bare parent heading was indexed"

    assert any(
        "thirty-seven" in chunk for chunk in chunks
    )


def test_a_short_but_real_clause_survives():
    """
    The threshold is measured, not guessed. In this corpus
    every bare heading has a 0-character body and the
    shortest real clause has 100, so the cut sits just above
    zero. Putting it mid-gap would silently discard policy.
    """

    chunks = structure_aware_chunk_text(
        "5 Records\n"
        "Records are kept for six years.\n"
    )

    assert len(chunks) == 1
    assert "six years" in chunks[0]


# ---------------- page breaks ----------------------


def test_a_clause_spanning_a_page_break_stays_whole():
    """
    Chunking page by page cut any clause that spanned a
    page boundary. HR-201 section 3 produced a chunk reading
    only "the first day back at work." - the tail of a
    sentence whose head was on the previous page, indexed as
    though it were a clause.
    """

    from app.services.chunker import (
        structure_aware_chunk_documents,
    )

    pages = [
        {
            "text": (
                "3.1 Reporting Absence\n"
                "An employee who cannot attend must "
                "tell their manager before"
            ),
            "source_file": "HR-201.pdf",
            "page_number": 1,
        },
        {
            "text": (
                " the first day back at work.\n"
                "3.2 Unauthorised Absence\n"
                "Absence not notified is treated as "
                "unauthorised."
            ),
            "source_file": "HR-201.pdf",
            "page_number": 2,
        },
    ]

    chunks = structure_aware_chunk_documents(pages)

    texts = [chunk["text"] for chunk in chunks]

    assert not any(
        text.strip().startswith("the first day")
        for text in texts
    ), "a page-break fragment was indexed as a clause"

    reporting = next(
        text
        for text in texts
        if text.startswith("3.1")
    )

    assert "first day back at work" in reporting


def test_a_split_clause_is_cited_by_its_first_page():
    """
    A section spanning two pages is cited by where it
    begins, which is how someone reading the PDF would cite
    it.
    """

    from app.services.chunker import (
        structure_aware_chunk_documents,
    )

    pages = [
        {
            "text": (
                "3.1 Reporting Absence\n"
                "An employee who cannot attend must "
                "tell their manager before"
            ),
            "source_file": "HR-201.pdf",
            "page_number": 1,
        },
        {
            "text": " the first day back at work.",
            "source_file": "HR-201.pdf",
            "page_number": 2,
        },
    ]

    chunks = structure_aware_chunk_documents(pages)

    assert chunks[0]["page_number"] == 1
