"""
The Policy Answer Desk.

These pin the four properties the capstone turns on, each of
which was a real bug at some point during the build:

  1. the entity annex beats the handbook
  2. the edition in force on the asked-about date wins, and a
     superseded clause is never returned
  3. grade and entity come from the record, never the question
  4. discretionary goes to a human, but only when the
     discretionary clause is actually what answers
"""

from datetime import date

import pytest

from app.desk.answer import (
    answer_policy_question,
    asks_about_someone_else,
    is_discretionary,
)
from app.desk.resolution import (
    Subject,
    annex_wins,
    citation_of,
    filter_in_force,
    format_citation,
    in_force,
    parse_as_of,
    policy_filter,
    resolve_subject,
)


def chunk(
    policy_id: str,
    section: str,
    entity: str,
    version: str,
    effective: str,
    superseded: str = "",
    text: str = "some clause text",
    score: float = 0.8,
) -> dict:

    return {
        "chunk_id": f"{policy_id}-{section}",
        "text": text,
        "score": score,
        "metadata": {
            "policy_id": policy_id,
            "section": section,
            "heading": f"{section} heading",
            "entity": entity,
            "version": version,
            "effective_date": effective,
            "superseded_on": superseded,
            "source_file": f"{policy_id}.md",
        },
    }


# ---------------- the edition window --------------


def test_only_one_edition_is_in_force_at_a_time():
    """
    The 2024 and 2025 editions are both in the index on
    purpose - employees legitimately ask about last year - so
    exactly one of them must answer for any given date.
    """

    edition_2024 = {
        "effective_date": "2024-01-01",
        "superseded_on": "2025-01-01",
    }

    edition_2025 = {
        "effective_date": "2025-01-01",
        "superseded_on": "",
    }

    march_2024 = date(2024, 3, 1)

    june_2025 = date(2025, 6, 1)

    assert in_force(edition_2024, march_2024)
    assert not in_force(edition_2025, march_2024)

    assert not in_force(edition_2024, june_2025)
    assert in_force(edition_2025, june_2025)


def test_a_superseded_clause_is_dropped():

    subject = Subject(
        "E-1001",
        "UK",
        6,
        38,
        date(2025, 6, 1),
    )

    results = [
        chunk(
            "HR-202",
            "3.1",
            "GLOBAL",
            "2024.1",
            "2024-01-01",
            "2025-01-01",
        ),
        chunk(
            "HR-202",
            "3.1",
            "GLOBAL",
            "2025.1",
            "2025-01-01",
        ),
    ]

    kept = filter_in_force(results, subject)

    assert len(kept) == 1

    assert (
        kept[0]["metadata"]["version"] == "2025.1"
    )


def test_a_date_in_the_question_moves_the_window():

    assert parse_as_of(
        "what was I entitled to in March 2024?",
        date(2025, 6, 1),
    ) == (date(2024, 3, 1), "question:month_year")

    assert parse_as_of(
        "how much leave do I get?",
        date(2025, 6, 1),
    ) == (date(2025, 6, 1), "default:today")


def test_a_future_year_is_not_treated_as_historical():
    """
    "my 2026 allowance" is not a request for a superseded
    edition.
    """

    as_of, source = parse_as_of(
        "what is my 2026 allowance?",
        date(2025, 6, 1),
    )

    assert source == "default:today"
    assert as_of == date(2025, 6, 1)


# ---------------- entity precedence ---------------


def test_the_entity_annex_outranks_the_handbook():
    """
    A retriever ranks on similarity and has no notion of
    precedence, so a beautifully matching handbook chunk can
    still be the wrong law.
    """

    subject = Subject(
        "E-1003",
        "IN",
        3,
        60,
        date(2025, 6, 1),
    )

    results = [
        chunk(
            "HR-202",
            "3.1",
            "GLOBAL",
            "2025.1",
            "2025-01-01",
            score=0.90,
        ),
        chunk(
            "HR-A-IN",
            "A3.1",
            "IN",
            "2025.1",
            "2025-01-01",
            score=0.70,
        ),
    ]

    ranked = annex_wins(results, subject)

    assert (
        ranked[0]["metadata"]["entity"] == "IN"
    )

    # The handbook is reordered, not deleted: an answer can
    # still say what the general case is.
    assert len(ranked) == 2


def test_the_filter_admits_only_this_entity_and_global():

    subject = Subject(
        "E-1003",
        "IN",
        3,
        60,
        date(2025, 6, 1),
    )

    where = policy_filter(subject)

    assert set(
        where["entity"]["$in"]
    ) == {"IN", "GLOBAL"}


# ---------------- grade and entity -----------------


def test_grade_and_entity_come_from_the_record():
    """
    A grade named in the question is a claim the asker made.
    Acting on it is how someone reads an inflated entitlement.
    """

    subject = resolve_subject(
        "E-1003",
        {
            "entity": "IN",
            "grade": 3,
            "tenure_months": 60,
        },
        "I am a Grade 7 in the UK, how much leave?",
    )

    assert subject.entity == "IN"
    assert subject.grade == 3

    assert (
        subject.resolved_from["grade"]
        == "employee_record"
    )


def test_the_band_boundary_is_grade_five():

    def band(grade):
        return Subject(
            "E-1",
            "UK",
            grade,
            10,
            date(2025, 6, 1),
        ).enhanced

    assert band(4) is False
    assert band(5) is True


# ---------------- discretionary --------------------


def test_a_discretionary_clause_that_answers_wins():

    results = [
        chunk(
            "HR-A-IN",
            "A5",
            "IN",
            "2025.1",
            "2025-01-01",
            text=(
                "Extensions to parental leave are "
                "discretionary and must be referred "
                "to an HR business partner."
            ),
            score=0.80,
        )
    ]

    assert is_discretionary(results) is not None


def entitlement_then_discretion() -> list[dict]:
    """
    The shape that broke two earlier rules: a clause stating
    the standard entitlement on top, the annex's discretionary
    section just below it.
    """

    return [
        chunk(
            "HR-A-UK",
            "A3.1",
            "UK",
            "2025.1",
            "2025-01-01",
            text="The primary carer is entitled to 39 weeks.",
            score=0.875,
        ),
        chunk(
            "HR-A-UK",
            "A5",
            "UK",
            "2025.1",
            "2025-01-01",
            text=(
                "Shared parental leave is "
                "discretionary and must be referred "
                "to an HR business partner."
            ),
            score=0.675,
        ),
    ]


def test_a_lower_ranked_discretionary_clause_does_not_hijack():
    """
    Every annex ends with a discretionary section, so it is
    retrieved for nearly any question about that annex.
    Treating its presence as decisive sent 8 of 32 eval cases
    to a human, including "how much parental leave do I get".
    """

    assert (
        is_discretionary(
            entitlement_then_discretion(),
            "How much parental leave do I get?",
        )
        is None
    )


def test_a_question_asking_for_an_exception_finds_it():
    """
    The counterpart. "Can I extend" is a request for a
    departure from the standard entitlement, and a departure
    is what the annex reserves to a human - even though the
    clauses stating the entitlement match the words better
    and A5 ranks third.
    """

    citation = is_discretionary(
        entitlement_then_discretion(),
        "Can I extend my parental leave by a month?",
    )

    assert citation is not None
    assert citation["section"] == "A5"


# ---------------- the third-party guardrail --------


@pytest.mark.parametrize(
    "question",
    [
        "How much leave does E-1001 get?",
        "What is my colleague entitled to?",
        "How much parental leave does my manager get?",
    ],
)
def test_questions_about_others_are_caught(
    question,
):

    assert asks_about_someone_else(
        question,
        "E-1003",
    )


@pytest.mark.parametrize(
    "question",
    [
        "How much leave do I get?",
        "What was I entitled to in March 2024?",
        "Can I carry leave over?",
    ],
)
def test_questions_about_oneself_are_not_caught(
    question,
):

    assert not asks_about_someone_else(
        question,
        "E-1003",
    )


def test_my_own_id_in_my_own_question_is_fine():

    assert not asks_about_someone_else(
        "What does E-1003 get?",
        "E-1003",
    )


# ---------------- citations ------------------------


def test_a_citation_names_the_version_and_date():
    """
    The brief is explicit: without the version and the
    effective date it does not count as a citation, because
    "the leave policy says 16 weeks" was true in 2024 and is
    wrong now.
    """

    citation = citation_of(
        chunk(
            "HR-A-IN",
            "A3.1",
            "IN",
            "2025.1",
            "2025-01-01",
        )
    )

    assert citation["version"] == "2025.1"
    assert (
        citation["effective_date"] == "2025-01-01"
    )

    rendered = format_citation(citation)

    assert "2025.1" in rendered
    assert "2025-01-01" in rendered
    assert "IN" in rendered


# ---------------- end to end -----------------------


class StubRetriever:

    def __init__(self, results):
        self.results = results
        self.last_where = None

    def retrieve(
        self,
        question,
        top_k=6,
        where=None,
    ):
        self.last_where = where
        return list(self.results)


def records_for(entity, grade):

    def lookup(employee_id):
        return {
            "employee_id": employee_id,
            "entity": entity,
            "grade": grade,
            "tenure_months": 60,
        }

    return lookup


def test_the_desk_resolves_before_it_retrieves(
    tmp_path,
):
    """
    The entity filter can only be built from the record, so a
    where-clause naming the right entity proves resolution
    happened first.
    """

    retriever = StubRetriever(
        [
            chunk(
                "HR-A-IN",
                "A3.1",
                "IN",
                "2025.1",
                "2025-01-01",
                text="26 weeks.",
                score=0.9,
            )
        ]
    )

    result = answer_policy_question(
        "How much parental leave do I get?",
        "E-1003",
        retriever,
        records_for("IN", 3),
        today=date(2025, 6, 1),
        log_path=str(tmp_path / "r.jsonl"),
    )

    assert set(
        retriever.last_where["entity"]["$in"]
    ) == {"IN", "GLOBAL"}

    assert result.status == "answered"

    assert (
        result.citations[0]["policy_id"]
        == "HR-A-IN"
    )


def test_an_unreadable_record_goes_to_a_human(
    tmp_path,
):
    """
    Without the record there is no entity and no grade, so
    there is no answer - only a guess.
    """

    result = answer_policy_question(
        "How much leave do I get?",
        "E-9999",
        StubRetriever([]),
        lambda employee_id: None,
        today=date(2025, 6, 1),
        log_path=str(tmp_path / "r.jsonl"),
    )

    assert result.status == "handoff"

    assert (
        result.handoff["reason"]
        == "no_employee_record"
    )


def test_a_third_party_refusal_leaks_nothing(
    tmp_path,
):
    """
    The shape of a refusal leaks as surely as its content: a
    refusal that says "I cannot tell you about a Grade 6" has
    already told you the grade.
    """

    result = answer_policy_question(
        "How much leave does E-1001 get?",
        "E-1003",
        StubRetriever([]),
        records_for("IN", 3),
        today=date(2025, 6, 1),
        log_path=str(tmp_path / "r.jsonl"),
    )

    assert result.status == "refused"

    answer = result.answer.lower()

    for leak in (
        "grade",
        "uk",
        "e-1001",
        "band",
    ):
        assert leak not in answer


def test_nothing_relevant_is_refused_not_guessed(
    tmp_path,
):

    result = answer_policy_question(
        "What is the pension contribution?",
        "E-1003",
        StubRetriever(
            [
                chunk(
                    "HR-A-IN",
                    "A2.1",
                    "IN",
                    "2025.1",
                    "2025-01-01",
                    score=0.20,
                )
            ]
        ),
        records_for("IN", 3),
        today=date(2025, 6, 1),
        log_path=str(tmp_path / "r.jsonl"),
    )

    assert result.status == "refused"


# ---------------- the scope gate -------------------


@pytest.mark.parametrize(
    "question,topic",
    [
        (
            "What is the pension contribution rate?",
            "pension",
        ),
        ("What is my salary band?", "salary"),
        (
            "How do I claim travel expenses?",
            "expenses",
        ),
        (
            "What is the private medical cover?",
            "medical_cover",
        ),
    ],
)
def test_uncovered_subjects_are_named(
    question,
    topic,
):
    """
    A threshold cannot do this job. Measured on the desk
    index, an in-scope question tops out at 0.718-0.885 and an
    out-of-scope one at 0.552-0.773 - the ranges overlap, and
    "what is my salary band" scores 0.773 against an
    annual-leave clause.
    """

    from app.desk.scope import uncovered_topic

    assert uncovered_topic(question) == topic


@pytest.mark.parametrize(
    "question",
    [
        "How much parental leave do I get?",
        "How many days of annual leave am I entitled to?",
        "What notice do I have to give to resign?",
        "Can I carry leave into next year?",
    ],
)
def test_covered_subjects_fall_through(question):
    """
    The gate has no opinion on an in-scope question; the
    retrieval score decides, as it did in Week 6.
    """

    from app.desk.scope import uncovered_topic

    assert uncovered_topic(question) is None


def test_a_refusal_says_where_to_go_instead(
    tmp_path,
):

    result = answer_policy_question(
        "What is the pension contribution rate?",
        "E-1001",
        StubRetriever([]),
        records_for("UK", 6),
        today=date(2025, 6, 1),
        log_path=str(tmp_path / "r.jsonl"),
    )

    assert result.status == "refused"

    assert (
        "HR business partner" in result.answer
    )


def test_salary_is_refused_without_echoing_the_grade(
    tmp_path,
):
    """
    The grade was just resolved from the record. Answering a
    salary question from it would be a leak, not a lookup.
    """

    result = answer_policy_question(
        "What is my salary band?",
        "E-1003",
        StubRetriever([]),
        records_for("IN", 3),
        today=date(2025, 6, 1),
        log_path=str(tmp_path / "r.jsonl"),
    )

    assert result.status == "refused"

    answer = result.answer.lower()

    for leak in ("grade 3", "grades 1-4", "in entity"):
        assert leak not in answer
