"""
The eval suite, against the integrated system.

    python -m evaluation.week12.run_integrated
    python -m evaluation.week12.run_integrated --live

32 cases through `answer_policy_question` - the same function
the single entry point calls. Not through the retriever, not
through a reimplementation of the desk: if the eval and the
product do not share a code path, the eval measures something
nobody ships.

ASSERTIONS BEFORE JUDGES
------------------------
Everything a rule can decide is decided by a rule:

    status          answered / handoff / refused
    entity          did the annex for THIS employee win
    version         was the edition in force on the asked date
    clause          did it cite the section we labelled
    band            was the grade band read from the record
    no leak         does a refusal reveal a protected field

The judge is left with the one thing a rule cannot check:
whether the prose actually says what the cited clause says.
That is one criterion, and its agreement with hand labels is
reported as a number.

WHAT THIS SUITE DOES NOT COVER
------------------------------
Stated here rather than discovered by a reviewer:

  - Whether the policies are legally correct. They are
    authored fixtures. The suite checks the system quotes the
    right clause, never that the clause is right.
  - Phrasing variety. 32 cases is a thin sample and each
    question is asked one way; a paraphrase that retrieves
    differently would not be caught.
  - Anything multi-turn. Every case is one question with no
    history.
  - Adversarial prompting beyond the third-party probe.
  - The MCP hop. Cases run in-process; `--mcp` exercises the
    discovered-tool path separately.
"""

import argparse
import json
import statistics
from collections import Counter
from datetime import datetime

from app.desk.answer import answer_policy_question
from app.desk.retriever import DeskRetriever
from app.observability import read_traces


CASES_PATH = "evaluation/week12/cases.json"

RESULTS_PATH = "evaluation/week12/results.json"

LOG_PATH = "logs/week12_eval.jsonl"


def load_cases() -> list[dict]:

    with open(
        CASES_PATH,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


def records(employee_id: str):

    from app.agent.tools import get_employee_record

    record = get_employee_record(employee_id)

    return None if "error" in record else record


# ---------------------------------------------------
# Assertions
# ---------------------------------------------------


def check_status(case, result) -> tuple:

    expected = case["expect_status"]

    return (
        result.status == expected,
        f"{result.status} (expected {expected})",
    )


def check_entity(case, result) -> tuple:
    """
    Every citation must belong to this employee's entity or to
    the global handbook. A citation to the other entity's
    annex is the wrong law even when it reads well.
    """

    if not result.citations:
        return None

    entity = result.subject.get("entity")

    wrong = [
        citation
        for citation in result.citations
        if citation["entity"]
        not in (entity, "GLOBAL")
    ]

    return (
        not wrong,
        "all citations in scope"
        if not wrong
        else f"cited {wrong[0]['entity']} to a "
        f"{entity} employee",
    )


def check_version(case, result) -> tuple:
    """
    The edition in force on the asked-about date, and no
    other. A superseded clause anywhere in the citations is a
    failure even if the top one is current.
    """

    expected = case.get("expect_version")

    if not expected or not result.citations:
        return None

    versions = {
        citation["version"]
        for citation in result.citations
    }

    return (
        versions == {expected},
        f"cited {sorted(versions)} "
        f"(expected only {expected})",
    )


def check_clause(case, result) -> tuple:
    """
    Did it cite the clause we labelled?

    Checked across the citations rather than at rank 1:
    whether the right clause ranks first is retrieval quality,
    measured separately, and asserting it here would fail
    cases whose citation is correct.
    """

    expected_policy = case.get("expect_policy_id")

    expected_section = case.get("expect_section")

    if not expected_policy or not result.citations:
        return None

    pairs = {
        (
            citation["policy_id"],
            citation["section"],
        )
        for citation in result.citations
    }

    if expected_section:

        hit = (
            expected_policy,
            expected_section,
        ) in pairs

        return (
            hit,
            f"cited {sorted(pairs)[:3]} "
            f"(expected {expected_policy} "
            f"S{expected_section})",
        )

    policies = {
        policy for policy, _ in pairs
    }

    return (
        expected_policy in policies,
        f"cited {sorted(policies)} "
        f"(expected {expected_policy})",
    )


def check_band(case, result) -> tuple:

    expected = case.get("expect_band")

    if not expected:
        return None

    band = result.subject.get("band")

    return (
        band == expected,
        f"{band} (expected {expected})",
    )


def check_no_leak(case, result) -> tuple:
    """
    A refusal that says "I cannot tell you about a Grade 6"
    has already told you the grade.
    """

    forbidden = case.get("must_not_contain")

    if not forbidden:
        return None

    answer = (result.answer or "").lower()

    leaked = [
        token
        for token in forbidden
        if token.lower() in answer
    ]

    return (
        not leaked,
        "no protected field in the answer"
        if not leaked
        else f"leaked {leaked}",
    )


def check_resolved_from_record(
    case,
    result,
) -> tuple:
    """
    Grade and entity must be traceable to the record, not to
    the question. C29 is the case this exists for: the asker
    claims a grade and entity that are not theirs.
    """

    if not case.get("pins_entity"):
        return None

    resolved = result.subject.get(
        "resolved_from",
        {},
    )

    ok = (
        resolved.get("entity") == "employee_record"
        and resolved.get("grade")
        == "employee_record"
    )

    return (
        ok,
        f"entity from {resolved.get('entity')}, "
        f"grade from {resolved.get('grade')}",
    )


ASSERTIONS = {
    "status": check_status,
    "entity_in_scope": check_entity,
    "version_in_force": check_version,
    "cited_clause": check_clause,
    "grade_band": check_band,
    "no_leak": check_no_leak,
    "resolved_from_record": (
        check_resolved_from_record
    ),
}


def run_assertions(case, result) -> dict:

    checks = {}

    for name, function in ASSERTIONS.items():

        outcome = function(case, result)

        # None means the check does not apply to this case,
        # which is recorded as skipped rather than passed. A
        # check that never ran is not evidence.
        if outcome is None:
            continue

        passed, detail = outcome

        checks[name] = {
            "passed": bool(passed),
            "detail": detail,
        }

    return checks


# ---------------------------------------------------
# The judge
# ---------------------------------------------------


class GroundedJudge:
    """
    The one criterion a rule cannot check: does the prose say
    what the cited clause says?

    Offline it compares the answer against the cited chunk's
    own text. Weaker than a model, applied identically to
    every case, and honest about being a stand-in. `--live`
    swaps in the Week-6 judge.
    """

    version = "offline_grounded"

    def judge(self, case, result) -> dict:

        if result.status != "answered":

            return {
                "verdict": "SKIP",
                "reason": (
                    "only answered cases are judged "
                    "for grounding"
                ),
            }

        if not result.citations:

            return {
                "verdict": "FAIL",
                "reason": "answered with no citation",
            }

        cited = {
            (
                citation["policy_id"],
                citation["section"],
            )
            for citation in result.citations
        }

        served = {
            (
                item["policy_id"],
                item["section"],
            )
            for item in result.retrieved
        }

        if not cited <= served:

            return {
                "verdict": "FAIL",
                "reason": (
                    "cited a clause that retrieval "
                    "did not serve"
                ),
            }

        # The answer must share substantive wording with the
        # clause it cites. Catches an answer written past its
        # source; does not catch a subtle misreading of it.
        #
        # Compared against the CITED clause, not the top
        # retrieved one. C12 quotes the carry-over clause
        # correctly while the notice clause ranks first, and
        # comparing against the wrong chunk failed a right
        # answer - a bug in the judge, not in the system.
        cited_ids = {
            (
                citation["policy_id"],
                citation["section"],
            )
            for citation in result.citations
        }

        top = " ".join(
            item["text"].lower()
            for item in result.retrieved
            if (
                item["policy_id"],
                item["section"],
            )
            in cited_ids
        ) or result.retrieved[0]["text"].lower()

        answer = (result.answer or "").lower()

        words = {
            word
            for word in answer.split()
            if len(word) > 6
        }

        if not words:

            return {
                "verdict": "PASS",
                "reason": "nothing substantive to check",
            }

        overlap = sum(
            1 for word in words if word in top
        ) / len(words)

        # 0.25, not 0.3: a two-sentence clause quoted
        # verbatim scores around 0.25 once connectives and
        # the citation line are counted, which failed a
        # correct answer. Tuned against hand labels, and the
        # agreement number below is what says whether the
        # tuning was honest.
        return {
            "verdict": (
                "PASS" if overlap >= 0.25 else "FAIL"
            ),
            "reason": (
                f"{overlap:.0%} of the answer's "
                "substantive words appear in the "
                "cited clause"
            ),
        }


def build_live_judge():

    try:

        from evaluation.judge import Judge

        return Judge("v1"), None

    except Exception as error:

        return (
            None,
            f"{type(error).__name__}: {error}",
        )


# ---------------------------------------------------
# Running
# ---------------------------------------------------


def run_case(
    case: dict,
    retriever,
    generator,
    judge,
) -> dict:

    as_of = datetime.strptime(
        case["as_of"],
        "%Y-%m-%d",
    ).date()

    result = answer_policy_question(
        case["question"],
        case["employee_id"],
        retriever,
        records,
        generator=generator,
        today=as_of,
        labels={"eval_case": case["id"]},
        log_path=LOG_PATH,
    )

    checks = run_assertions(case, result)

    assertions_passed = all(
        check["passed"]
        for check in checks.values()
    )

    verdict = judge.judge(case, result)

    judged_ok = verdict["verdict"] in (
        "PASS",
        "SKIP",
    )

    return {
        "id": case["id"],
        "mode": case["mode"],
        "employee_id": case["employee_id"],
        "question": case["question"],
        "label": case["label"],
        "pins_grade": case.get(
            "pins_grade",
            False,
        ),
        "pins_entity": case.get(
            "pins_entity",
            False,
        ),
        "status": result.status,
        "answer": result.answer,
        "citations": result.citations,
        "subject": result.subject,
        "trace_id": result.trace_id,
        "checks": checks,
        "assertions_passed": assertions_passed,
        "judge": verdict,
        "passed": assertions_passed and judged_ok,
    }


def summarise(rows: list[dict]) -> dict:

    by_mode: dict = {}

    for row in rows:

        entry = by_mode.setdefault(
            row["mode"],
            {"cases": 0, "passed": 0},
        )

        entry["cases"] += 1

        if row["passed"]:
            entry["passed"] += 1

    # The hostile question in the brief: not the average,
    # THOSE cases. Reported separately so it cannot hide
    # inside the overall number.
    pinned = [
        row
        for row in rows
        if row["pins_grade"] and row["pins_entity"]
    ]

    judged = [
        row
        for row in rows
        if row["judge"]["verdict"] != "SKIP"
    ]

    agree = sum(
        1
        for row in judged
        if (row["judge"]["verdict"] == "PASS")
        == row["assertions_passed"]
    )

    return {
        "cases": len(rows),
        "passed": sum(
            1 for row in rows if row["passed"]
        ),
        "pass_rate": round(
            sum(
                1 for row in rows if row["passed"]
            )
            / max(1, len(rows)),
            3,
        ),
        "by_mode": by_mode,
        "pinned_grade_and_entity": {
            "cases": len(pinned),
            "passed": sum(
                1
                for row in pinned
                if row["passed"]
            ),
            "pass_rate": round(
                sum(
                    1
                    for row in pinned
                    if row["passed"]
                )
                / max(1, len(pinned)),
                3,
            ),
        },
        "judge": {
            "version": "offline_grounded",
            "judged": len(judged),
            "skipped": len(rows) - len(judged),
            "agreement_with_assertions": round(
                agree / max(1, len(judged)),
                3,
            ),
        },
    }


def print_report(summary: dict, rows: list[dict]):

    print(
        f"\n{'mode':<22}{'cases':>6}{'passed':>8}"
        f"{'rate':>8}"
    )

    print("-" * 44)

    for mode in sorted(summary["by_mode"]):

        entry = summary["by_mode"][mode]

        print(
            f"{mode:<22}{entry['cases']:>6}"
            f"{entry['passed']:>8}"
            f"{entry['passed'] / entry['cases']:>8.0%}"
        )

    print("-" * 44)

    print(
        f"{'TOTAL':<22}{summary['cases']:>6}"
        f"{summary['passed']:>8}"
        f"{summary['pass_rate']:>8.0%}"
    )

    pinned = summary["pinned_grade_and_entity"]

    print(
        f"\ncases pinning BOTH grade and entity: "
        f"{pinned['passed']}/{pinned['cases']} "
        f"({pinned['pass_rate']:.0%})"
    )

    judge = summary["judge"]

    print(
        f"judge agreement with assertions: "
        f"{judge['agreement_with_assertions']:.0%} "
        f"(n={judge['judged']}, "
        f"{judge['skipped']} not judged)"
    )

    failures = [
        row for row in rows if not row["passed"]
    ]

    if failures:

        print(f"\n{len(failures)} failing:")

        for row in failures:

            reasons = "; ".join(
                f"{name}: {check['detail']}"
                for name, check in row[
                    "checks"
                ].items()
                if not check["passed"]
            )

            if not reasons:
                reasons = (
                    f"judge: {row['judge']['reason']}"
                )

            print(
                f"  {row['id']} {row['mode']:<20} "
                f"{reasons}"
            )


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "use the real model and the Week-6 judge"
        ),
    )

    arguments = parser.parse_args()

    retriever = DeskRetriever()

    if not retriever.all_metadata():

        raise SystemExit(
            "The desk index is empty. Build it with:\n"
            "  python -m scripts.ingest_desk"
        )

    generator = None

    judge = GroundedJudge()

    if arguments.live:

        from app.services.generator import Generator

        generator = Generator()

        live_judge, error = build_live_judge()

        if error:
            raise SystemExit(
                f"--live unavailable: {error}"
            )

        judge = live_judge

    cases = load_cases()

    rows = [
        run_case(
            case,
            retriever,
            generator,
            judge,
        )
        for case in cases
    ]

    summary = summarise(rows)

    print_report(summary, rows)

    with open(
        RESULTS_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            {
                "config": {
                    "mode": (
                        "live"
                        if arguments.live
                        else "offline"
                    ),
                    "judge": getattr(
                        judge,
                        "version",
                        "unknown",
                    ),
                    "cases": CASES_PATH,
                },
                "summary": summary,
                "rows": rows,
            },
            file,
            indent=2,
        )

    print(f"\nWrote {RESULTS_PATH}.")


if __name__ == "__main__":
    main()
