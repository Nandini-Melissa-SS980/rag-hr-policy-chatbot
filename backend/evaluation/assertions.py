"""
Deterministic checks, moved out of the judge.

Each of these was a criterion a model could have
been asked to grade. A rule does it for free, the
same way every time, so the judge is left with the
one thing a rule cannot check: whether the answer
is actually right.

Every function returns (passed, detail) so a failing
case explains itself in the report.
"""


def sources_present(
    sources: list[dict],
) -> tuple[bool, str]:
    """
    An answer that cites nothing cannot be checked
    by anyone, so this is a hard failure.
    """

    if sources:
        return True, f"{len(sources)} source(s)"

    return False, "no sources cited"


def sections_resolve(
    sources: list[dict],
    valid_sections: set[tuple[str, str]],
) -> tuple[bool, str]:
    """
    Every cited (policy_id, section) must exist in
    the index. Catches a citation to a section that
    was never in the documents.
    """

    if not sources:
        return False, "no sources to resolve"

    unresolved = []

    for source in sources:

        key = (
            source.get("policy_id", ""),
            source.get("section", ""),
        )

        if key not in valid_sections:
            unresolved.append(
                f"{key[0]}/{key[1]}"
            )

    if unresolved:
        return False, (
            "unresolved: "
            + ", ".join(unresolved)
        )

    return True, "all sections resolve"


def refusal_is_correct(
    abstained: bool,
    expect_refusal: bool,
) -> tuple[bool, str]:
    """
    A question the documents do not cover must take
    the refusal path, and a question they do cover
    must not.
    """

    if abstained == expect_refusal:

        return True, (
            "refused"
            if abstained
            else "answered"
        )

    if expect_refusal:
        return False, (
            "answered a question the documents "
            "do not cover"
        )

    return False, "refused a covered question"


def run_assertions(
    case: dict,
    abstained: bool,
    sources: list[dict],
    valid_sections: set[tuple[str, str]],
    has_answer: bool = True,
) -> dict:
    """
    All assertions for one case.

    A refused case is not asked for citations,
    because a refusal has none. Nor is a case that
    produced no answer at all - a missing answer is
    a blocked check, not a failed one.
    """

    results = {}

    results["refusal_is_correct"] = (
        refusal_is_correct(
            abstained,
            case["expect_refusal"],
        )
    )

    if (
        case["expect_refusal"]
        or abstained
        or not has_answer
    ):
        return results

    results["sources_present"] = (
        sources_present(sources)
    )

    results["sections_resolve"] = (
        sections_resolve(
            sources,
            valid_sections,
        )
    )

    return results


def all_passed(
    results: dict,
) -> bool:

    return all(
        passed
        for passed, _ in results.values()
    )
