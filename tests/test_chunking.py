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
        extract_policy_id("HR-207.pdf")
        == "HR-207"
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
