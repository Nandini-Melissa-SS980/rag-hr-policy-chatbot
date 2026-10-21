"""
Push the existing log into LangSmith.

    python -m evaluation.week11.to_langsmith

New requests export themselves as they are logged. This is for
the traces already on disk - without it the project starts
empty and the drill has nothing to show.

Reads `logs/requests.jsonl` and replays every row through the
same exporter the live path uses, so a backfilled run and a
live one are identical in LangSmith.

Needs a key:

    LANGSMITH_API_KEY=ls__...     in backend/.env
    python -m evaluation.week11.to_langsmith
"""

import argparse
import os
import sys

from app.observability import REQUESTS_LOG, read_traces


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--path",
        default=REQUESTS_LOG,
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="export only the most recent N",
    )

    arguments = parser.parse_args()

    # Convenience: running this module at all means you want
    # the export, so the flag is implied rather than required.
    os.environ.setdefault(
        "LANGSMITH_ENABLED",
        "1",
    )

    from app.langsmith_export import (
        LANGSMITH_PROJECT,
        export_trace,
        get_client,
    )

    traces = read_traces(arguments.path)

    if not traces:

        raise SystemExit(
            f"No traces in {arguments.path}. Run: "
            "python -m evaluation.week11.seed_logs"
        )

    if arguments.limit:
        traces = traces[-arguments.limit :]

    if get_client() is None:

        raise SystemExit(
            "LangSmith is unavailable. Set "
            "LANGSMITH_API_KEY in backend/.env - get "
            "one from https://smith.langchain.com"
        )

    sent = 0

    for trace in traces:

        if export_trace(trace):
            sent += 1

    print(
        f"Exported {sent}/{len(traces)} traces to "
        f"project '{LANGSMITH_PROJECT}'."
    )

    if sent < len(traces):

        print(
            f"{len(traces) - sent} failed - see the "
            "messages above.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
