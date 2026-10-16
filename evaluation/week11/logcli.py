"""
The log search the support drill runs.

    python -m evaluation.week11.logcli --answer "notice"
    python -m evaluation.week11.logcli --day tue
    python -m evaluation.week11.logcli --trace R-7f3c1a9e4d2b
    python -m evaluation.week11.logcli --cost-outliers

Each flag is one slice. The point of having several
is that a vague complaint names a different one each
time: "maybe Tuesday" is a time slice, "quoted 30
days" is an output slice, "it was slow" is a latency
slice.

--answer is the slice that matters here and the one
most often missing. A complaint describes what the
user saw, not what they typed, so searching inputs
alone would mean reading 197 answers by hand. drill.md
reports what having it was worth in mm:ss.
"""

import argparse
import json
from datetime import datetime

from app.observability import (
    REQUESTS_LOG,
    read_traces,
)


DAYS = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


def parse_day(value: str) -> int:

    key = value.strip().lower()[:3]

    if key not in DAYS:

        raise SystemExit(
            f"Unknown day: {value}. Use one of "
            f"{', '.join(DAYS)}."
        )

    return DAYS[key]


def weekday_of(trace: dict) -> int:

    return datetime.fromisoformat(
        trace["started_at"]
    ).weekday()


def matches(
    trace: dict,
    arguments,
) -> bool:

    if arguments.trace and trace[
        "trace_id"
    ] != arguments.trace:
        return False

    if arguments.day is not None and (
        weekday_of(trace) != arguments.day
    ):
        return False

    if arguments.user and trace.get(
        "labels",
        {},
    ).get("user") != arguments.user:
        return False

    if (
        arguments.prompt_version
        and trace.get("prompt_version")
        != arguments.prompt_version
    ):
        return False

    if arguments.question and (
        arguments.question.lower()
        not in trace["question"].lower()
    ):
        return False

    if arguments.answer and (
        arguments.answer.lower()
        not in (trace.get("answer") or "").lower()
    ):
        return False

    if arguments.context and arguments.context not in (
        trace.get("context_ids") or []
    ):
        return False

    return True


def summarise(trace: dict) -> str:

    started = datetime.fromisoformat(
        trace["started_at"]
    )

    return (
        f"{trace['trace_id']}  "
        f"{started.strftime('%a %d %b %H:%M')}  "
        f"{trace.get('prompt_version', '-'):<4} "
        f"${trace.get('cost_usd', 0):.6f}  "
        f"{trace.get('duration_ms', 0):>7.1f}ms  "
        f"Q: {trace['question'][:46]}"
        + (
            ""
            if len(trace["question"]) <= 46
            else "..."
        )
        + f"\n{'':>14}A: "
        + (trace.get("answer") or "")[:70]
        + (
            ""
            if len(trace.get("answer") or "")
            <= 70
            else "..."
        )
    )


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--trace")

    parser.add_argument(
        "--day",
        type=parse_day,
    )

    parser.add_argument("--user")

    parser.add_argument("--prompt-version")

    parser.add_argument(
        "--question",
        help="substring of the INPUT",
    )

    parser.add_argument(
        "--answer",
        help="substring of the OUTPUT",
    )

    parser.add_argument(
        "--context",
        help="a chunk_id that was retrieved",
    )

    parser.add_argument(
        "--cost-outliers",
        action="store_true",
        help=(
            "the ten most expensive requests"
        ),
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="print the whole trace as JSON",
    )

    parser.add_argument(
        "--path",
        default=REQUESTS_LOG,
    )

    arguments = parser.parse_args()

    traces = read_traces(arguments.path)

    if not traces:

        raise SystemExit(
            f"No traces in {arguments.path}. "
            "Run: python -m "
            "evaluation.week11.seed_logs"
        )

    if arguments.cost_outliers:

        found = sorted(
            traces,
            key=lambda trace: -trace.get(
                "cost_usd",
                0,
            ),
        )[:10]

    else:

        found = [
            trace
            for trace in traces
            if matches(trace, arguments)
        ]

    print(
        f"{len(found)} of {len(traces)} "
        "request(s)\n"
    )

    for trace in found:

        if arguments.full:

            print(
                json.dumps(trace, indent=2)
            )

        else:
            print(summarise(trace))
            print()


if __name__ == "__main__":
    main()
