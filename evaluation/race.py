"""
The race: agent versus fixed workflow.

    python -m evaluation.race
    python -m evaluation.race --budget-demo

Same 10 questions, same three tools, same model, same
output contract. Four numbers per system: pass rate,
p50 latency, total tokens, cost per question.

--budget-demo needs no API. It drives the loop with a
stub that never stops calling tools, to show the
budgets terminating a run cleanly.
"""

import csv
import json
import statistics
import sys

from app.agent.loop import (
    Budgets,
    run_agent,
)
from app.agent.workflow import run_workflow
from app.config import (
    INPUT_COST_PER_1M,
    OPENAI_MODEL,
    OUTPUT_COST_PER_1M,
)


QUESTIONS_PATH = (
    "evaluation/race_questions.json"
)

CSV_PATH = "evaluation/race.csv"

RESULTS_PATH = "evaluation/race_results.json"

BUDGET_LOG_PATH = (
    "evaluation/budget_termination.log"
)


def load_questions() -> list[dict]:

    with open(
        QUESTIONS_PATH,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


def value_matches(
    actual,
    expected: str,
) -> bool:
    """
    Deterministic pass/fail on the key figure, so
    the race needs no judge.
    """

    if actual is None:
        return False

    got = str(actual).strip().lower()

    want = expected.strip().lower()

    if want.isdigit():

        digits = [
            part
            for part in "".join(
                character
                if character.isdigit()
                else " "
                for character in got
            ).split()
        ]

        return want in digits

    return want in got


def summarise(
    rows: list[dict],
) -> dict:

    if not rows:
        return {}

    passes = sum(
        1
        for row in rows
        if row["passed"]
    )

    tokens = sum(
        row["total_tokens"]
        for row in rows
    )

    cost = sum(
        row["cost_usd"] for row in rows
    )

    return {
        "questions": len(rows),
        "pass_rate": round(
            passes / len(rows),
            3,
        ),
        "p50_latency_s": round(
            statistics.median(
                row["seconds"]
                for row in rows
            ),
            3,
        ),
        "total_tokens": tokens,
        "cost_per_question_usd": round(
            cost / len(rows),
            6,
        ),
    }


def build_model_call():

    try:

        from app.agent.model import (
            make_model_call,
        )

        return make_model_call(), None

    except Exception as error:

        return None, (
            f"{type(error).__name__}: {error}"
        )


def race_one(
    system: str,
    runner,
    question: dict,
    model_call,
) -> dict:

    try:

        result = runner(
            question["question"],
            model_call,
        )

        error = None

    except Exception as failure:

        result = {
            "value": None,
            "answer": "",
            "seconds": 0.0,
            "iterations": 0,
            "terminated_by": None,
            "usage": {
                "total_tokens": 0,
                "cost_usd": 0.0,
            },
        }

        error = (
            f"{type(failure).__name__}: "
            f"{failure}"
        )

    return {
        "system": system,
        "id": question["id"],
        "branching": question["branching"],
        "expected": question[
            "expected_value"
        ],
        "value": result["value"],
        "passed": value_matches(
            result["value"],
            question["expected_value"],
        ),
        "seconds": result["seconds"],
        "iterations": result["iterations"],
        "terminated_by": result[
            "terminated_by"
        ],
        "total_tokens": result["usage"][
            "total_tokens"
        ],
        "cost_usd": result["usage"][
            "cost_usd"
        ],
        "answer": result["answer"],
        "error": error,
    }


def print_table(summaries: dict):

    print(
        f"\n{'system':<10}"
        f"{'pass':>7}"
        f"{'p50 s':>9}"
        f"{'tokens':>10}"
        f"{'$/question':>13}"
    )

    print("-" * 49)

    for system, summary in summaries.items():

        if not summary:
            continue

        print(
            f"{system:<10}"
            f"{summary['pass_rate']:>7}"
            f"{summary['p50_latency_s']:>9}"
            f"{summary['total_tokens']:>10}"
            f"{summary['cost_per_question_usd']:>13}"
        )

    print("-" * 49)

    if (
        INPUT_COST_PER_1M == 0
        and OUTPUT_COST_PER_1M == 0
    ):
        print(
            "\nCost is 0.00 because token prices "
            "are unset. Set INPUT_COST_PER_1M and "
            "OUTPUT_COST_PER_1M in .env from the "
            "provider's pricing page."
        )


def write_csv(rows: list[dict]):

    fields = [
        "system",
        "id",
        "branching",
        "expected",
        "value",
        "passed",
        "seconds",
        "iterations",
        "total_tokens",
        "cost_usd",
        "terminated_by",
        "error",
    ]

    with open(
        CSV_PATH,
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore",
        )

        writer.writeheader()

        writer.writerows(rows)


def looping_stub(
    instructions,
    items,
    tools,
) -> dict:
    """
    A model that never finishes: it asks for the same
    tool forever. Exactly what the budgets exist for.
    """

    return {
        "tool_calls": [
            {
                "call_id": (
                    f"call_{len(items)}"
                ),
                "name": "get_employee_record",
                "arguments": {
                    "employee_id": "E-1002"
                },
            }
        ],
        "text": None,
        "input_tokens": 1200,
        "output_tokens": 80,
    }


def budget_demo():
    """
    Runs the loop against the stub under two
    different budgets, so the log shows which one
    fired rather than just that something stopped.
    """

    scenarios = [
        (
            "max_iterations fires first",
            Budgets(
                max_iterations=4,
                max_tokens=1_000_000,
                max_cost_usd=0.0,
                max_seconds=600,
            ),
        ),
        (
            "max_tokens fires first",
            Budgets(
                max_iterations=50,
                max_tokens=3_000,
                max_cost_usd=0.0,
                max_seconds=600,
            ),
        ),
    ]

    lines = [
        "Budget termination demo",
        "",
        "Driven by a stub model that always "
        "requests another tool call, so the run "
        "can only end on a budget. No API needed.",
    ]

    for title, budgets in scenarios:

        result = run_agent(
            "What notice period must E-1002 give?",
            looping_stub,
            budgets,
        )

        lines.extend(
            [
                "",
                "=" * 52,
                title,
                "=" * 52,
                f"budgets: iterations="
                f"{budgets.max_iterations} "
                f"tokens={budgets.max_tokens} "
                f"cost={budgets.max_cost_usd} "
                f"seconds={budgets.max_seconds}",
                "",
                *result["log"],
                "",
                f"terminated_by : "
                f"{result['terminated_by']}",
                f"iterations    : "
                f"{result['iterations']}",
                f"total_tokens  : "
                f"{result['usage']['total_tokens']}",
                f"answer        : "
                f"{result['answer']}",
            ]
        )

        print(
            f"{title}: terminated_by="
            f"{result['terminated_by']} after "
            f"{result['iterations']} iteration(s), "
            f"{result['usage']['total_tokens']} "
            "tokens"
        )

    with open(
        BUDGET_LOG_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        file.write("\n".join(lines) + "\n")

    print(f"\nWrote {BUDGET_LOG_PATH}.")


def main():

    if "--budget-demo" in sys.argv:
        budget_demo()
        return

    questions = load_questions()

    model_call, error = build_model_call()

    if error:
        print(f"Model unavailable: {error}")

    rows = []

    for question in questions:

        for system, runner in [
            ("agent", run_agent),
            ("workflow", run_workflow),
        ]:

            row = race_one(
                system,
                runner,
                question,
                model_call,
            )

            rows.append(row)

            print(
                f"{row['id']} {system:<9} "
                f"passed={row['passed']} "
                f"{row['seconds']}s "
                f"{row['total_tokens']} tokens"
                + (
                    f" [{row['error']}]"
                    if row["error"]
                    else ""
                )
            )

    summaries = {
        system: summarise(
            [
                row
                for row in rows
                if row["system"] == system
            ]
        )
        for system in ["agent", "workflow"]
    }

    print_table(summaries)

    write_csv(rows)

    with open(
        RESULTS_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            {
                "config": {
                    "model": OPENAI_MODEL,
                    "input_cost_per_1m": (
                        INPUT_COST_PER_1M
                    ),
                    "output_cost_per_1m": (
                        OUTPUT_COST_PER_1M
                    ),
                },
                "summary": summaries,
                "rows": rows,
            },
            file,
            indent=2,
        )

    print(
        f"\nWrote {CSV_PATH} and {RESULTS_PATH}."
    )


if __name__ == "__main__":
    main()
