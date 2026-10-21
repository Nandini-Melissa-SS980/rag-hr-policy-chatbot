"""
Per-request logging: traces, spans, and the fields
the support drill slices on.

If it isn't logged, it didn't happen. What makes a
complaint like "it quoted the wrong notice period,
maybe Tuesday" findable is not one big log line, it
is a small number of fields that can each be sliced:

    trace_id        a found request can be replayed
    started_at      "maybe Tuesday" becomes a filter
    question        the INPUT is searchable
    answer          the OUTPUT is searchable
    prompt_version  "the model changed" is checkable
    context_ids     retrieval and generation can be
                    told apart when the answer is wrong
    spans           cost and latency per stage, not
                    one lump

The output field is the one most often missed and the
one that matters most here. A complaint describes
what the user SAW, not what they typed, so an index
over inputs alone leaves you grepping. Both are
indexed; drill.md reports what that was worth in
mm:ss.

Storage is a JSONL file, which is the right size for
this app: appendable, greppable, replayable, no
service to run. Spans carry the shape OpenTelemetry
uses - name, duration, attributes - so moving to a
real collector later is a writer change, not a schema
change.
"""

import json
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.config import BASE_DIR, OPENAI_MODEL


LOG_DIR = os.path.join(BASE_DIR, "logs")

REQUESTS_LOG = os.path.join(
    LOG_DIR,
    "requests.jsonl",
)


def token_cost(
    input_tokens: int,
    output_tokens: int,
) -> float:
    """
    Priced from the same .env figures the Week-8 and
    Week-10 tables use, so one logged row's cost is
    on the same scale as the race numbers.
    """

    from app.config import (
        INPUT_COST_PER_1M,
        OUTPUT_COST_PER_1M,
    )

    return (
        input_tokens
        / 1_000_000
        * INPUT_COST_PER_1M
        + output_tokens
        / 1_000_000
        * OUTPUT_COST_PER_1M
    )


@dataclass
class Span:
    """
    One stage of one request.

    `stage` is what cost is attributed to: retrieval,
    generation or tools. A span with no tokens still
    has a duration, which is how retrieval shows up
    as latency without showing up as spend.
    """

    name: str

    stage: str

    start: float = 0.0

    duration_ms: float = 0.0

    input_tokens: int = 0

    output_tokens: int = 0

    attributes: dict = field(
        default_factory=dict
    )

    error: str | None = None

    @property
    def cost_usd(self) -> float:

        return token_cost(
            self.input_tokens,
            self.output_tokens,
        )

    def as_dict(self) -> dict:

        return {
            "name": self.name,
            "stage": self.stage,
            "duration_ms": round(
                self.duration_ms,
                2,
            ),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": (
                self.input_tokens
                + self.output_tokens
            ),
            "cost_usd": round(
                self.cost_usd,
                8,
            ),
            "attributes": self.attributes,
            "error": self.error,
        }


@dataclass
class Trace:
    """
    One request, end to end.
    """

    trace_id: str

    question: str

    prompt_version: str

    started_at: str

    model: str = OPENAI_MODEL

    spans: list = field(default_factory=list)

    answer: str = ""

    sources: list = field(
        default_factory=list
    )

    context_ids: list = field(
        default_factory=list
    )

    abstained: bool = False

    duration_ms: float = 0.0

    error: str | None = None

    # Free-form, for whoever is calling: a user id, a
    # channel, an eval case id. Sliceable like any
    # other field.
    labels: dict = field(
        default_factory=dict
    )

    def span(
        self,
        name: str,
        stage: str,
        **attributes,
    ):
        """
        Replaced by the recorder's bound version when
        a trace is opened through `Recorder`. Present
        here so a hand-built Trace is still usable.
        """

        return _span_context(
            self,
            name,
            stage,
            attributes,
        )

    @property
    def input_tokens(self) -> int:

        return sum(
            span.input_tokens
            for span in self.spans
        )

    @property
    def output_tokens(self) -> int:

        return sum(
            span.output_tokens
            for span in self.spans
        )

    @property
    def cost_usd(self) -> float:

        return sum(
            span.cost_usd
            for span in self.spans
        )

    def cost_by_stage(self) -> dict:
        """
        The breakdown the Week-11 rubric asks for.
        Optimising before attributing means not being
        able to say which change moved the number.
        """

        stages: dict = {}

        for span in self.spans:

            entry = stages.setdefault(
                span.stage,
                {
                    "duration_ms": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0.0,
                },
            )

            entry["duration_ms"] += (
                span.duration_ms
            )

            entry["input_tokens"] += (
                span.input_tokens
            )

            entry["output_tokens"] += (
                span.output_tokens
            )

            entry["cost_usd"] += span.cost_usd

        for entry in stages.values():

            entry["duration_ms"] = round(
                entry["duration_ms"],
                2,
            )

            entry["cost_usd"] = round(
                entry["cost_usd"],
                8,
            )

        return stages

    def as_dict(self) -> dict:

        return {
            "trace_id": self.trace_id,
            "started_at": self.started_at,
            "model": self.model,
            "prompt_version": (
                self.prompt_version
            ),
            # Input and output are both indexed. A
            # complaint describes the output far more
            # often than the input.
            "question": self.question,
            "answer": self.answer,
            "abstained": self.abstained,
            "sources": self.sources,
            # The field whose absence turns a one-hop
            # diagnosis into a two-day mystery: did
            # retrieval serve the wrong passage, or
            # did the model ignore the right one?
            "context_ids": self.context_ids,
            "duration_ms": round(
                self.duration_ms,
                2,
            ),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": (
                self.input_tokens
                + self.output_tokens
            ),
            "cost_usd": round(
                self.cost_usd,
                8,
            ),
            "cost_by_stage": (
                self.cost_by_stage()
            ),
            "spans": [
                span.as_dict()
                for span in self.spans
            ],
            "labels": self.labels,
            "error": self.error,
        }


@contextmanager
def _span_context(
    trace: Trace,
    name: str,
    stage: str,
    attributes: dict,
):

    span = Span(
        name=name,
        stage=stage,
        start=time.perf_counter(),
        attributes=dict(attributes),
    )

    trace.spans.append(span)

    try:
        yield span

    except Exception as error:

        span.error = (
            f"{type(error).__name__}: {error}"
        )

        raise

    finally:

        span.duration_ms = (
            time.perf_counter() - span.start
        ) * 1000


class Recorder:
    """
    Opens a trace, times its spans, appends it.

        with Recorder(question, "v2") as trace:
            with trace.span("retrieve", "retrieval"):
                ...
    """

    def __init__(
        self,
        question: str,
        prompt_version: str,
        trace_id: str | None = None,
        labels: dict | None = None,
        path: str = REQUESTS_LOG,
        started_at: str | None = None,
    ):

        self.path = path

        self.started = 0.0

        self.trace = Trace(
            trace_id=trace_id
            or f"R-{uuid.uuid4().hex[:12]}",
            question=question,
            prompt_version=prompt_version,
            started_at=started_at
            or datetime.now(
                timezone.utc
            ).isoformat(),
            labels=labels or {},
        )

    def __enter__(self) -> Trace:

        self.started = time.perf_counter()

        return self.trace

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):

        self.trace.duration_ms = (
            time.perf_counter() - self.started
        ) * 1000

        if exc is not None:

            self.trace.error = (
                f"{exc_type.__name__}: {exc}"
            )

        write_trace(self.trace, self.path)

        # Never swallow the caller's exception. A
        # logged failure is still a failure.
        return False


def write_trace(
    trace: Trace,
    path: str = REQUESTS_LOG,
):
    """
    Append one trace to the log, then mirror it to LangSmith.

    The file is written first and unconditionally. It is the
    source of truth - the support drill greps it, it needs no
    service running, and it works with an unfunded key.
    LangSmith is a view on top, so an export failure must
    never cost us the row.
    """

    directory = os.path.dirname(path)

    if directory:
        os.makedirs(
            directory,
            exist_ok=True,
        )

    payload = trace.as_dict()

    with open(
        path,
        "a",
        encoding="utf-8",
    ) as file:

        file.write(json.dumps(payload) + "\n")

    # Off unless LANGSMITH_ENABLED=1, and it swallows its own
    # failures, so this is a no-op in the default setup.
    try:

        from app.langsmith_export import (
            export_trace,
        )

        export_trace(payload)

    except Exception:
        # Importing the exporter must not break logging even
        # if the LangSmith packages are not installed.
        pass


def read_traces(
    path: str = REQUESTS_LOG,
) -> list[dict]:

    if not os.path.exists(path):
        return []

    traces = []

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:

        for line in file:

            line = line.strip()

            if not line:
                continue

            try:
                traces.append(
                    json.loads(line)
                )

            except json.JSONDecodeError:
                continue

    return traces
