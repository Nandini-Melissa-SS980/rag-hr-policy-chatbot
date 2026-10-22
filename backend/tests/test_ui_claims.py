"""
Does the UI tell the truth about the corpus?

The Policies page asserts that certain subjects are NOT
covered. That is a claim about absence, and absence is
exactly the kind of claim that rots silently: someone
enriches a policy, a new clause mentions expenses, and a
page nobody re-read now says something false.

The expenses claim did rot. HR-206 gained an "Equipment and
Expenses" section, and the page still said expenses were not
covered - while a question about a desk allowance retrieved
that clause at 0.777 and answered it.
"""

import pymupdf
import pytest

from app.config import ADDENDA_DIR


def corpus_text() -> str:

    import os

    chunks = []

    for name in sorted(os.listdir(ADDENDA_DIR)):

        if not name.endswith(".pdf"):
            continue

        document = pymupdf.open(
            os.path.join(ADDENDA_DIR, name)
        )

        chunks.append(
            "\n".join(
                page.get_text() for page in document
            )
        )

        document.close()

    return "\n".join(chunks).lower()


@pytest.mark.parametrize(
    "subject",
    [
        "maternity",
        "pension scheme",
        "private medical",
        "training budget",
    ],
)
def test_subjects_the_ui_calls_uncovered_really_are(
    subject,
):
    """
    Each of these appears in the page's "Not covered" list.

    A bare mention inside a disclaimer is fine - HR-201 S4
    says these are not covered, which is the corpus agreeing
    with the page. What must not exist is a clause that
    actually answers the question.
    """

    text = corpus_text()

    # Sentences that mention the subject while saying it is
    # NOT covered are the page agreeing with itself.
    disclaimed = (
        "not covered" in text
        or "outside this policy" in text
    )

    assert subject not in text or disclaimed, (
        f"{subject!r} appears in the corpus outside a "
        "disclaimer, so the Not covered list is wrong"
    )


def test_expenses_are_partly_covered_and_the_ui_says_so():
    """
    The one the audit caught. HR-206 S5 states the home
    office allowance, so "expenses" cannot be listed as
    simply not covered.

    This test exists to fail if someone moves it back.
    """

    text = corpus_text()

    assert "equipment and expenses" in text

    assert "home office allowance" in text


def test_the_policy_count_matches_the_corpus():
    """
    The page says "these N documents". N is rendered from
    the POLICIES list, and both must match the PDFs on disk.
    """

    import os

    pdfs = {
        name[:-4]
        for name in os.listdir(ADDENDA_DIR)
        if name.endswith(".pdf")
    }

    assert pdfs == {
        "HR-201",
        "HR-202",
        "HR-203",
        "HR-204",
        "HR-205",
        "HR-206",
    }
