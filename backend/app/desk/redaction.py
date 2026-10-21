"""
Keep protected fields out of the log.

WHO READS THIS LOG
------------------
`logs/*.jsonl` is readable by everyone with the repo. The
support drill depends on that: a complaint is found by
grepping it. So the question is not "is this field sensitive"
but "would I be comfortable with the whole squad reading this
line about a named colleague".

For three fields the answer is no:

    grade          an employee's grade band
    tenure         months of service
    leave_balance  days remaining

Each is a fact about a person that nobody needs in order to
debug a retrieval problem. `employee_id` IS logged - it is the
identifier the drill searches on, and without it a complaint
about a past answer cannot be found at all.

WHAT IS NOT REDACTED, AND WHY
-----------------------------
`entity` on a CITATION is a property of the document, not of
the person: `HR-A-IN` is the India annex whoever reads it. It
stays, because a trace that cannot say which annex was cited
cannot be audited.

The employee's own entity is a different matter and is not
logged as a value - the tool span records
`entity_resolved: true` and nothing more.

THE LEAK THIS FOUND
-------------------
The extractive answer ended "...which applies to you as
grades 1-4 in the IN entity", and the answer is logged. 272
violations across 192 traces, caught by auditing the raw log
rather than by reading the redaction policy. The answer the
employee sees still says it; the answer that reaches the log
does not.
"""

import re


# The band phrasing the desk writes into an extractive answer.
BAND_PHRASE = re.compile(
    r",?\s*which applies to you as grades \d-\d"
    r" in the [A-Z]{2} entity\.?",
    re.IGNORECASE,
)

# A bare band, anywhere.
BAND = re.compile(
    r"\bgrades? \d(?:-\d)?\b",
    re.IGNORECASE,
)

REDACTED = "[redacted]"


def redact_answer(answer: str) -> str:
    """
    The answer as it should appear in the log.

    The employee still receives the unredacted text - this is
    applied on the way to disk, not on the way to the user.
    """

    if not answer:
        return answer

    cleaned = BAND_PHRASE.sub("", answer)

    return BAND.sub(REDACTED, cleaned)


# Fields that must never be logged as values, wherever they
# appear in a nested structure.
PROTECTED_FIELDS = (
    "grade",
    "band",
    "tenure_months",
    "leave_balance",
    "salary",
    "manager_comment",
)


def redact_subject(subject: dict) -> dict:
    """
    The resolved subject, minus the protected values.

    What stays is the shape of the resolution - that an entity
    and a grade WERE resolved, and from where - because that
    is what a trace needs to show the record was read before
    the answer was decided.
    """

    if not subject:
        return subject

    return {
        "employee_id": subject.get("employee_id"),
        "as_of": subject.get("as_of"),
        "resolved_from": subject.get(
            "resolved_from",
            {},
        ),
        "entity_resolved": bool(
            subject.get("entity")
        ),
        "grade_resolved": subject.get("grade")
        is not None,
    }


def audit(payload: str) -> list[str]:
    """
    Find protected values in a serialised trace.

    Used by the test that pins this, and runnable over a real
    log file. The brief's hostile question is "show me one raw
    log line" - this is the check that makes the answer to
    that question safe to give.
    """

    found = []

    for pattern, name in (
        (r'"grade"\s*:\s*\d', "grade value"),
        (r"\bgrades \d-\d\b", "band value"),
        (
            r'"tenure_months"\s*:\s*\d',
            "tenure value",
        ),
        (
            r'"leave_balance"\s*:',
            "leave balance",
        ),
        (
            r'"manager_comment"\s*:',
            "manager comment",
        ),
    ):

        if re.search(pattern, payload):
            found.append(name)

    return found
