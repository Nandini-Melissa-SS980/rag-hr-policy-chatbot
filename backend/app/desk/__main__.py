"""
The Policy Answer Desk - single entry point.

    python -m app.desk --employee E-1003 "How much parental leave do I get?"
    python -m app.desk --employee E-1001 "What was I entitled to in March 2024?"
    python -m app.desk --demo

One command, the whole system: the employee record resolves
grade and entity, retrieval is filtered to that entity and to
the edition in force, the entity annex outranks the handbook,
discretionary matters go to an HR business partner, and every
hop lands on one trace id.

`--mcp` routes the record lookup and the policy search over
MCP instead of calling them in-process, so the same command
exercises the discovered-at-runtime path.
"""

import argparse
import json
import sys
from datetime import date, datetime

from app.desk.answer import answer_policy_question
from app.desk.retriever import DeskRetriever


def local_records(employee_id: str):
    """
    The employee record, read in-process from the fixture.
    """

    from app.agent.tools import get_employee_record

    record = get_employee_record(employee_id)

    return None if "error" in record else record


def build_generator(live: bool):

    if not live:
        return None, None

    try:

        from app.services.generator import Generator

        return Generator(), None

    except Exception as error:

        return (
            None,
            f"{type(error).__name__}: {error}",
        )


# The four questions the demo runs, chosen so that each one
# exercises a different decision and no two can be answered the
# same way. A demo question with one answer regardless of who
# asks proves nothing.
DEMO = [
    (
        "E-1003",
        "How much parental leave do I get as the primary carer?",
        "India, grade 3 - the India annex overrides the handbook",
    ),
    (
        "E-1001",
        "How much parental leave do I get as the primary carer?",
        "UK, grade 6 - same question, different entity AND grade",
    ),
    (
        "E-1001",
        "What was I entitled to for parental leave in March 2024?",
        "the 2024 edition, because the question asks about 2024",
    ),
    (
        "E-1003",
        "Can I extend my parental leave by a month?",
        "discretionary - handed to an HR business partner",
    ),
]


def run_one(
    employee_id: str,
    question: str,
    retriever,
    generator,
    today,
    as_json: bool,
) -> dict:

    result = answer_policy_question(
        question,
        employee_id,
        retriever,
        local_records,
        generator=generator,
        today=today,
    )

    if as_json:
        return result.as_dict()

    subject = result.subject

    print(f"\n  Q  {question}")

    print(f"  .. employee {employee_id}", end="")

    if subject:
        print(
            f" -> entity {subject['entity']}, "
            f"grade {subject['grade']} "
            f"({subject['band']}), "
            f"as of {subject['as_of']}"
        )
    else:
        print()

    print(f"  => [{result.status}]")

    for line in result.answer.split("\n"):
        print(f"     {line}")

    if result.citations:

        print("     citations:")

        for citation in result.citations:
            print(
                f"       {citation['policy_id']} "
                f"S{citation['section']} "
                f"v{citation['version']} "
                f"eff {citation['effective_date']} "
                f"[{citation['entity']}]"
            )

    print(f"     trace {result.trace_id}")

    return result.as_dict()


def main():

    parser = argparse.ArgumentParser(
        prog="python -m app.desk",
        description=(
            "Policy Answer Desk - ask one policy "
            "question as one employee."
        ),
    )

    parser.add_argument(
        "question",
        nargs="?",
        help="the policy question",
    )

    parser.add_argument(
        "--employee",
        help="employee id, for example E-1003",
    )

    parser.add_argument(
        "--today",
        help=(
            "pretend today is this date, YYYY-MM-DD, "
            "so the version window is testable"
        ),
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "use the real model to phrase the answer; "
            "without it the clause is returned "
            "verbatim with its citation"
        ),
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="run the four demo questions",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="machine-readable output",
    )

    arguments = parser.parse_args()

    today = (
        datetime.strptime(
            arguments.today,
            "%Y-%m-%d",
        ).date()
        if arguments.today
        else None
    )

    retriever = DeskRetriever()

    if not retriever.all_metadata():

        raise SystemExit(
            "The desk index is empty. Build it with:\n"
            "  python -m scripts.ingest_desk"
        )

    generator, error = build_generator(
        arguments.live
    )

    if error:
        print(
            f"Model unavailable ({error}); "
            "answering from the clause itself.",
            file=sys.stderr,
        )

    if arguments.demo:

        results = []

        for (
            employee_id,
            question,
            why,
        ) in DEMO:

            if not arguments.json:
                print(f"\n-- {why}")

            results.append(
                run_one(
                    employee_id,
                    question,
                    retriever,
                    generator,
                    today,
                    arguments.json,
                )
            )

        if arguments.json:
            print(json.dumps(results, indent=2))

        else:
            print()

        return

    if not arguments.question or not arguments.employee:

        parser.error(
            "give a question and --employee, or use "
            "--demo"
        )

    result = run_one(
        arguments.employee,
        arguments.question,
        retriever,
        generator,
        today,
        arguments.json,
    )

    if arguments.json:
        print(json.dumps(result, indent=2))

    else:
        print()


if __name__ == "__main__":
    main()
