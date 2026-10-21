"""
Resolve WHO is asking and WHICH policy applies, before
retrieving anything.

Three facts decide whether an entitlement answer is right, and
none of them is in any document:

    entity   India or UK - the annex overrides the handbook
    grade    1-7 - which band of the entitlement applies
    as_of    the date the answer must be correct for, which
             picks the edition in force then

All three come from the employee record and the question, and
they are resolved FIRST. Retrieving before resolving is how a
correctly cited clause becomes a different employee's answer.

THE FILTER IS ENFORCED, NOT HOPED FOR
-------------------------------------
`policy_filter` builds a Chroma `where` clause. A chunk from
the wrong entity or a superseded edition is never returned, so
it cannot rank well and cannot be cited. The alternative -
retrieving everything and trusting the model to notice the
dates in the prose - is the failure this module exists to
prevent.

The one deliberate exception is a historical question. An
employee asking what they were entitled to in March 2024 must
get the 2024 edition, so `as_of` moves the window rather than
pinning it to today.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
import re


# Entity codes as they appear in the employee record and in
# each annex's front matter. GLOBAL is the handbook: it is
# always in scope, and always loses to an annex.
ENTITIES = ("IN", "UK")

GLOBAL = "GLOBAL"

ENHANCED_FROM_GRADE = 5


# An explicit date in the question: "in March 2024", "as of
# 2024-03-01", "on 1 March 2024". Only used when the employee
# is asking about a past entitlement.
ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

MONTH_YEAR = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    r"[a-z]*\s+(\d{4})\b",
    re.IGNORECASE,
)

BARE_YEAR = re.compile(r"\b(20\d{2})\b")

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


@dataclass
class Subject:
    """
    Who the answer is for, and when it has to be correct for.

    `resolved_from` records where each fact came from, because
    "the record said grade 3" and "the asker said grade 3" are
    different claims and only one of them is evidence.
    """

    employee_id: str

    entity: str

    grade: int

    tenure_months: int

    as_of: date

    resolved_from: dict = field(
        default_factory=dict
    )

    @property
    def enhanced(self) -> bool:

        return self.grade >= ENHANCED_FROM_GRADE

    @property
    def band(self) -> str:

        return (
            f"grades {ENHANCED_FROM_GRADE}-7"
            if self.enhanced
            else f"grades 1-{ENHANCED_FROM_GRADE - 1}"
        )

    def as_dict(self) -> dict:

        return {
            "employee_id": self.employee_id,
            "entity": self.entity,
            "grade": self.grade,
            "band": self.band,
            "tenure_months": self.tenure_months,
            "as_of": self.as_of.isoformat(),
            "resolved_from": self.resolved_from,
        }


def parse_as_of(
    question: str,
    today: date | None = None,
) -> tuple[date, str]:
    """
    The date the answer must be correct for.

    Defaults to today. A question that names a past date gets
    that date instead, because "what was I entitled to in
    March 2024" is a legitimate question and deleting the 2024
    edition to avoid it would delete the test, not the bug.

    Returns (date, where_it_came_from).
    """

    today = today or date.today()

    match = ISO_DATE.search(question)

    if match:

        try:
            return (
                date(
                    int(match.group(1)),
                    int(match.group(2)),
                    int(match.group(3)),
                ),
                "question:iso_date",
            )

        except ValueError:
            pass

    match = MONTH_YEAR.search(question)

    if match:

        month = MONTHS[
            match.group(1)[:3].lower()
        ]

        return (
            date(int(match.group(2)), month, 1),
            "question:month_year",
        )

    # A bare year only counts when it is not this year -
    # "in 2024" is historical, "my 2026 allowance" is not a
    # request for a superseded edition.
    match = BARE_YEAR.search(question)

    if match:

        year = int(match.group(1))

        if year < today.year:

            return (
                date(year, 7, 1),
                "question:bare_year",
            )

    return today, "default:today"


def resolve_subject(
    employee_id: str,
    record: dict,
    question: str,
    today: date | None = None,
) -> Subject:
    """
    Build the Subject from the employee record.

    Entity and grade come from the record and from nowhere
    else. A grade named in the question is a claim the asker
    made, and acting on it is how someone reads a colleague's
    entitlement - or their own, inflated.
    """

    as_of, as_of_source = parse_as_of(
        question,
        today,
    )

    return Subject(
        employee_id=employee_id,
        entity=record["entity"],
        grade=int(record["grade"]),
        tenure_months=int(
            record.get("tenure_months", 0)
        ),
        as_of=as_of,
        resolved_from={
            "entity": "employee_record",
            "grade": "employee_record",
            "tenure_months": "employee_record",
            "as_of": as_of_source,
        },
    )


def in_force(
    metadata: dict,
    as_of: date,
) -> bool:
    """
    Was this edition in force on `as_of`?

    In force from its effective_date until the day its
    successor takes over. `superseded_on` empty means current.
    """

    effective = _parse_iso(
        metadata.get("effective_date")
    )

    if effective is None or as_of < effective:
        return False

    superseded = _parse_iso(
        metadata.get("superseded_on")
    )

    return superseded is None or as_of < superseded


def _parse_iso(value) -> date | None:

    if not value or not isinstance(value, str):
        return None

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()

    except ValueError:
        return None


def policy_filter(subject: Subject) -> dict:
    """
    The Chroma `where` clause for this subject.

    Entity is enforced here. Version is not: Chroma cannot
    express "effective_date <= X and (superseded_on is empty
    or superseded_on > X)" as a single clause, so the date
    window is applied in `filter_in_force` after the search.
    Both are enforcement; only one of them is expressible in
    the query language.
    """

    return {
        "entity": {
            "$in": [subject.entity, GLOBAL]
        }
    }


def filter_in_force(
    results: list[dict],
    subject: Subject,
) -> list[dict]:
    """
    Drop editions that were not in force on `as_of`.

    Applied after retrieval because the date window cannot be
    expressed as a Chroma filter. The effect is the same: a
    superseded clause is removed before anything can cite it.
    """

    return [
        result
        for result in results
        if in_force(
            result.get("metadata", {}),
            subject.as_of,
        )
    ]


def annex_wins(
    results: list[dict],
    subject: Subject,
) -> list[dict]:
    """
    Where an entity annex and the handbook both answer, the
    annex wins.

    The handbook is the general case and says so; the annex
    says it overrides. A retriever ranks on similarity and has
    no notion of precedence, so a beautifully matching handbook
    chunk can still be the wrong law. This reorders rather than
    deletes: the handbook chunk stays available, below the
    annex, so an answer can still say what the general case is.
    """

    annex = [
        result
        for result in results
        if result.get("metadata", {}).get(
            "entity"
        )
        == subject.entity
    ]

    general = [
        result
        for result in results
        if result.get("metadata", {}).get(
            "entity"
        )
        != subject.entity
    ]

    return annex + general


def citation_of(result: dict) -> dict:
    """
    A citation that names the version and its effective date.

    The brief is explicit: without the version and the date it
    does not count as a citation, because "the leave policy
    says 16 weeks" was true in 2024 and is wrong now.
    """

    metadata = result.get("metadata", {})

    return {
        "policy_id": metadata.get("policy_id", ""),
        "section": metadata.get("section", ""),
        "heading": metadata.get("heading", ""),
        "version": metadata.get("version", ""),
        "effective_date": metadata.get(
            "effective_date",
            "",
        ),
        "entity": metadata.get("entity", ""),
        "source_file": metadata.get(
            "source_file",
            "",
        ),
    }


def format_citation(citation: dict) -> str:

    return (
        f"{citation['policy_id']} "
        f"S{citation['section']} "
        f"(v{citation['version']}, effective "
        f"{citation['effective_date']}, "
        f"{citation['entity']})"
    )
