"""
The one command.

    python -m evaluation.run_eval
    python -m evaluation.run_eval --judge-version v2

Runs every case in eval_set.json through the app,
applies the deterministic assertions, asks the judge
for the one criterion a rule cannot check, and prints
the pass rate per Week-5 failure mode.

A per-mode table is printed rather than one overall
number, because an average hides a regression in a
single mode.
"""

import json
import sys

from evaluation.assertions import (
    all_passed,
    run_assertions,
)
from evaluation.trace_capture import (
    STRATEGY,
    TOP_K,
    build_generator,
    describe_retrieved,
)
from app.services.retriever import Retriever


EVAL_SET_PATH = "evaluation/eval_set.json"

RESULTS_PATH = "evaluation/eval_results.json"

ASSERTION_NAMES = [
    "refusal_is_correct",
    "sources_present",
    "sections_resolve",
]

JUDGED_CRITERIA = [
    "policy_correctness",
]


def load_eval_set() -> list[dict]:

    with open(
        EVAL_SET_PATH,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


def valid_sections(
    retriever: Retriever,
) -> set[tuple[str, str]]:

    return {
        (
            metadata.get("policy_id", ""),
            metadata.get("section", ""),
        )
        for metadata in (
            retriever.vector_store.all_metadata()
        )
    }


def build_judge(version: str):
    """
    Returns the judge, or None with the reason it is
    unavailable.
    """

    try:

        from evaluation.judge import Judge

        return Judge(version), None

    except Exception as error:

        return None, (
            f"{type(error).__name__}: {error}"
        )


def run_case(
    case: dict,
    retriever: Retriever,
    sections: set[tuple[str, str]],
    generator,
    judge,
) -> dict:

    results = retriever.retrieve(
        case["question"],
        top_k=TOP_K,
    )

    abstained = not retriever.has_good_match(
        results
    )

    answer = None

    sources = []

    error = None

    if abstained:

        answer = (
            "I couldn't find information about "
            "this in the provided HR policy "
            "documents."
        )

    elif generator is None:

        error = "generator unavailable"

    else:

        try:

            generated = generator.generate(
                question=case["question"],
                results=results,
            )

            answer = generated.get("answer", "")

            sources = generated.get(
                "sources",
                [],
            )

        except Exception as failure:

            error = (
                f"{type(failure).__name__}: "
                f"{failure}"
            )

    assertions = run_assertions(
        case,
        abstained,
        sources,
        sections,
        has_answer=answer is not None,
    )

    verdict = None

    if judge is not None and answer:

        verdict = judge.judge(
            case["question"],
            answer,
            describe_retrieved(results),
        )

    return {
        "id": case["id"],
        "mode": case["mode"],
        "question": case["question"],
        "regression": case.get(
            "regression",
            False,
        ),
        "abstained": abstained,
        "answer": answer,
        "sources": sources,
        "error": error,
        "blocked": bool(error),
        "assertions": {
            name: {
                "passed": passed,
                "detail": detail,
            }
            for name, (
                passed,
                detail,
            ) in assertions.items()
        },
        "assertions_passed": all_passed(
            assertions
        ),
        "judge": verdict,
    }


def blank_counts() -> dict:
    """
    An assertion that never ran on a case is counted
    separately from one that ran and failed, so a
    missing answer cannot masquerade as a defect.
    """

    counts = {
        "cases": 0,
        "judge_pass": 0,
        "judged": 0,
    }

    for name in ASSERTION_NAMES:

        counts[name] = {
            "ran": 0,
            "passed": 0,
        }

    return counts


def summarise_by_mode(
    rows: list[dict],
) -> dict:

    modes = {}

    for row in rows:

        mode = modes.setdefault(
            row["mode"],
            blank_counts(),
        )

        mode["cases"] += 1

        for name in ASSERTION_NAMES:

            result = row["assertions"].get(
                name
            )

            if result is None:
                continue

            mode[name]["ran"] += 1

            if result["passed"]:
                mode[name]["passed"] += 1

        if row["judge"]:

            mode["judged"] += 1

            if row["judge"]["verdict"] == "PASS":
                mode["judge_pass"] += 1

    return modes


def rate(counts: dict) -> str:

    if not counts["ran"]:
        return "-"

    return (
        f"{counts['passed']}/{counts['ran']}"
    )


def print_table(
    modes: dict,
    rows: list[dict],
):

    header = (
        f"\n{'mode':<14}"
        f"{'cases':>6}"
        f"{'refusal':>9}"
        f"{'sources':>9}"
        f"{'sections':>10}"
        f"{'judged':>8}"
    )

    print(header)

    print("-" * 56)

    for mode in sorted(modes):

        counts = modes[mode]

        judged = (
            f"{counts['judge_pass']}/"
            f"{counts['judged']}"
            if counts["judged"]
            else "-"
        )

        print(
            f"{mode:<14}"
            f"{counts['cases']:>6}"
            f"{rate(counts['refusal_is_correct']):>9}"
            f"{rate(counts['sources_present']):>9}"
            f"{rate(counts['sections_resolve']):>10}"
            f"{judged:>8}"
        )

    print("-" * 56)

    blocked = sum(
        1
        for row in rows
        if row["blocked"]
    )

    print(
        f"{'TOTAL':<14}"
        f"{len(rows):>6}"
    )

    print(
        f"\nassertions: {len(ASSERTION_NAMES)} "
        f"({', '.join(ASSERTION_NAMES)})"
    )

    print(
        f"judged criteria: "
        f"{len(JUDGED_CRITERIA)} "
        f"({', '.join(JUDGED_CRITERIA)})"
    )

    if blocked:

        print(
            f"\n{blocked}/{len(rows)} cases have "
            "no answer, so the citation assertions "
            "and the judge could not run on them. "
            "A '-' is not a pass."
        )


def main():

    version = "v1"

    if "--judge-version" in sys.argv:

        version = sys.argv[
            sys.argv.index(
                "--judge-version"
            )
            + 1
        ]

    cases = load_eval_set()

    retriever = Retriever(STRATEGY)

    sections = valid_sections(retriever)

    generator, generator_error = (
        build_generator()
    )

    if generator_error:
        print(
            "Generator unavailable: "
            f"{generator_error}"
        )

    judge, judge_error = build_judge(version)

    if judge_error:
        print(
            f"Judge unavailable: {judge_error}"
        )

    rows = []

    for case in cases:

        row = run_case(
            case,
            retriever,
            sections,
            generator,
            judge,
        )

        rows.append(row)

        print(
            f"{row['id']} {row['mode']:<14} "
            f"assertions="
            f"{'pass' if row['assertions_passed'] else 'FAIL'}"
        )

    modes = summarise_by_mode(rows)

    print_table(modes, rows)

    report = {
        "config": {
            "strategy": STRATEGY,
            "top_k": TOP_K,
            "judge_version": version,
            "assertions": ASSERTION_NAMES,
            "judged_criteria": JUDGED_CRITERIA,
        },
        "by_mode": modes,
        "results": rows,
    }

    with open(
        RESULTS_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            report,
            file,
            indent=2,
        )

    print(f"\nWrote {RESULTS_PATH}.")


if __name__ == "__main__":
    main()
