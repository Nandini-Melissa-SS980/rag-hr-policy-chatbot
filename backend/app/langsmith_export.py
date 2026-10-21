"""
Ship traces to LangSmith.

The JSONL log stays the source of truth: it is what the
support drill greps, it needs no service running, and it works
with an unfunded key. LangSmith is the dashboard on top - a
run tree per request, retrieval inspection, token and cost
columns, and datasets built from real traffic.

HOW THIS MAPS
-------------
`app/observability.py` records a trace as one request with a
span per stage. LangSmith records a run tree: a parent run
with child runs. The shapes line up directly, so this module
is a translation of field names rather than a change to how
the app is instrumented. Nothing in the request path knows
LangSmith exists.

    our trace        -> a `chain` run     (question, answer)
      retrieval span -> a `retriever` run (documents)
      generation span-> an `llm` run      (token counts)

Run type is what makes LangSmith render retrieved chunks as
documents and tokens as a cost column, rather than as
anonymous key-value pairs on a generic run.

WHAT WAS AND WAS NOT ADOPTED
----------------------------
LangSmith, yes. LangChain, not in the request path.

LangSmith's usual route is `@traceable` or LangChain's own
auto-instrumentation, both of which assume LangChain owns the
retrieval and generation calls. Here they do not: the
retriever, the generator, the agent loop and its budgets are
hand built, and rewriting them as LCEL chains would delete the
parts of this project that the evals measure - the budget
termination log, the hand-off token accounting and the
trajectory eval all read structures LangChain would own.

So this module posts run trees directly with the `langsmith`
client, which needs no LangChain at all. The dashboard is
identical; what differs is that the instrumentation stays
explicit and the request path keeps its own shape. The
langchain packages in requirements.txt are there for
experimentation, not because anything here imports them.

TURNING IT ON
-------------
Off unless LANGSMITH_ENABLED=1, because a client that cannot
reach the service should never slow down or break a request.
Every failure here is swallowed and reported once.

    LANGSMITH_API_KEY=ls__...          # from smith.langchain.com
    LANGSMITH_ENABLED=1 uvicorn app.main:app --reload

The key is read from the environment and is never logged.
"""

import os
import uuid
from datetime import datetime, timezone

from app.config import OPENAI_MODEL


LANGSMITH_ENABLED = os.getenv(
    "LANGSMITH_ENABLED",
    "",
).lower() in ("1", "true", "yes")

LANGSMITH_PROJECT = os.getenv(
    "LANGSMITH_PROJECT",
    "hr360-bot",
)

LANGSMITH_ENDPOINT = os.getenv(
    "LANGSMITH_ENDPOINT",
    "https://api.smith.langchain.com",
)


# Set once, on first use. None means "not yet tried", False
# means "tried and unavailable" - remembered so a missing key
# or an unreachable service is reported once rather than per
# request.
_client = None

_failed = False


def _run_type(stage: str) -> str:
    """
    Our stage name -> the LangSmith run type.
    """

    return {
        "retrieval": "retriever",
        "generation": "llm",
        "tools": "tool",
    }.get(stage, "chain")


def get_client():
    """
    The LangSmith client, or None when export is off or
    unavailable.
    """

    global _client, _failed

    if not LANGSMITH_ENABLED or _failed:
        return None

    if _client is not None:
        return _client

    try:

        if not os.getenv("LANGSMITH_API_KEY"):

            raise RuntimeError(
                "LANGSMITH_API_KEY is not set. Get one "
                "from https://smith.langchain.com "
                "and put it in backend/.env"
            )

        from langsmith import Client

        _client = Client(
            api_url=LANGSMITH_ENDPOINT,
            api_key=os.getenv(
                "LANGSMITH_API_KEY"
            ),
        )

        return _client

    except Exception as error:

        _failed = True

        print(
            "LangSmith export unavailable, continuing "
            f"with the JSONL log only: "
            f"{type(error).__name__}: {error}"
        )

        return None


def _parse_time(iso: str):

    try:
        parsed = datetime.fromisoformat(iso)

    except (TypeError, ValueError):
        return datetime.now(timezone.utc)

    if parsed.tzinfo is None:
        return parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed


def _documents(context: list) -> list:
    """
    Retrieved chunks, in the shape LangSmith renders as
    documents on a `retriever` run.
    """

    return [
        {
            "page_content": item.get("text", "")
            or "",
            "metadata": {
                "chunk_id": item.get(
                    "chunk_id",
                    "",
                ),
                "policy_id": item.get(
                    "policy_id",
                    "",
                ),
                "section": item.get(
                    "section",
                    "",
                ),
                "score": item.get("score", 0.0),
            },
        }
        for item in context
    ]


def export_trace(trace_dict: dict) -> bool:
    """
    One logged request -> one LangSmith run tree.

    Takes the dict `Trace.as_dict()` already produces, so the
    exporter reads exactly what the JSONL file holds and the
    two can never describe different requests.

    Returns True when a run was posted. Never raises: a
    dashboard that is down must not fail a user's request.
    """

    client = get_client()

    if client is None:
        return False

    try:

        from langsmith.run_trees import RunTree

        started = _parse_time(
            trace_dict.get("started_at", "")
        )

        context = (
            (trace_dict.get("labels") or {}).get(
                "context"
            )
            or []
        )

        duration_ms = trace_dict.get(
            "duration_ms",
            0.0,
        )

        # The drill's slices, carried as metadata so they are
        # filterable in the LangSmith UI rather than only
        # visible on the run.
        metadata = {
            "trace_id": trace_dict.get("trace_id"),
            "prompt_version": trace_dict.get(
                "prompt_version"
            ),
            "abstained": trace_dict.get(
                "abstained"
            ),
            "cost_usd": trace_dict.get("cost_usd"),
            "context_ids": trace_dict.get(
                "context_ids",
                [],
            ),
            **{
                key: value
                for key, value in (
                    trace_dict.get("labels") or {}
                ).items()
                # The full context travels on the retriever
                # run instead.
                if key != "context"
            },
        }

        tags = [
            f"prompt:{trace_dict.get('prompt_version')}",
        ]

        if trace_dict.get("abstained"):
            tags.append("abstained")

        if trace_dict.get("error"):
            tags.append("error")

        root = RunTree(
            id=uuid.uuid4(),
            name="hr360.request",
            run_type="chain",
            project_name=LANGSMITH_PROJECT,
            inputs={
                "question": trace_dict.get(
                    "question",
                    "",
                )
            },
            outputs={
                "answer": trace_dict.get(
                    "answer",
                    "",
                )
                or "",
                "sources": trace_dict.get(
                    "sources",
                    [],
                ),
            },
            start_time=started,
            end_time=started
            + _delta(duration_ms),
            extra={"metadata": metadata},
            tags=tags,
            error=trace_dict.get("error"),
            client=client,
        )

        for span in trace_dict.get("spans", []):

            _add_child(root, span, context, started)

        # Posts the parent and walks the tree. The children
        # were created with `create_child`, so they already
        # carry the right parent and trace ids.
        root.post(exclude_child_runs=False)

        return True

    except Exception as error:

        print(
            "LangSmith export failed for "
            f"{trace_dict.get('trace_id')}: "
            f"{type(error).__name__}: {error}"
        )

        return False


def _delta(milliseconds: float):

    from datetime import timedelta

    return timedelta(
        milliseconds=max(0.0, milliseconds)
    )


def _add_child(
    root,
    span: dict,
    context: list,
    parent_started,
):

    stage = span.get("stage", "")

    run_type = _run_type(stage)

    inputs: dict = {}

    outputs: dict = {}

    if stage == "retrieval":

        inputs = {
            "query": root.inputs.get(
                "question",
                "",
            )
        }

        outputs = {
            "documents": _documents(context)
        }

    elif stage == "generation":

        inputs = {
            "prompt_version": (
                root.extra.get("metadata", {}).get(
                    "prompt_version"
                )
            ),
        }

        outputs = {
            "answer": root.outputs.get(
                "answer",
                "",
            ),
        }

    child = root.create_child(
        name=span.get("name", stage or "span"),
        run_type=run_type,
        inputs=inputs,
        start_time=parent_started,
        extra={
            "metadata": {
                "stage": stage,
                "cost_usd": span.get(
                    "cost_usd",
                    0.0,
                ),
                "duration_ms": span.get(
                    "duration_ms",
                    0.0,
                ),
                **(span.get("attributes") or {}),
            },
            # Token counts under the key LangSmith reads for
            # its own cost column.
            "invocation_params": {
                "model": (
                    span.get("attributes") or {}
                ).get("model", OPENAI_MODEL),
            },
        },
    )

    if stage == "generation":

        # LangSmith reads usage_metadata for its token and
        # cost columns, so the counts go in the outputs
        # rather than only in metadata.
        outputs["usage_metadata"] = {
            "input_tokens": span.get(
                "input_tokens",
                0,
            ),
            "output_tokens": span.get(
                "output_tokens",
                0,
            ),
            "total_tokens": span.get(
                "total_tokens",
                0,
            ),
        }

    child.end(
        outputs=outputs,
        error=span.get("error"),
        end_time=parent_started
        + _delta(span.get("duration_ms", 0.0)),
    )

    return child
