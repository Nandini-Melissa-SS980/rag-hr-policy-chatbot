import json
import os

from app.observability import (
    Recorder,
    Span,
    Trace,
    read_traces,
    token_cost,
)
from app.services.prompts import (
    CURRENT_PROMPT_VERSION,
    PROMPTS,
    get_prompt,
)
from evaluation.week11.topics import (
    covers_topic,
    question_topic,
)


# ---------------- spans and cost ------------------


def test_cost_splits_input_and_output():
    """
    Output is priced higher than input, so a span
    that mixes them cannot be costed by total alone.
    """

    assert token_cost(
        1_000_000,
        0,
    ) != token_cost(0, 1_000_000)


def test_a_span_with_no_tokens_still_costs_nothing():

    span = Span(
        name="retrieve",
        stage="retrieval",
    )

    assert span.cost_usd == 0.0


def test_cost_by_stage_groups_spans():
    """
    Attribution before optimisation: a lump total
    cannot say which stage a saving came from.
    """

    trace = Trace(
        trace_id="T1",
        question="q",
        prompt_version="v2",
        started_at="2025-11-04T14:37:00+00:00",
    )

    trace.spans.append(
        Span(
            name="retrieve",
            stage="retrieval",
            duration_ms=12.0,
        )
    )

    trace.spans.append(
        Span(
            name="generate",
            stage="generation",
            duration_ms=800.0,
            input_tokens=900,
            output_tokens=40,
        )
    )

    stages = trace.cost_by_stage()

    assert set(stages) == {
        "retrieval",
        "generation",
    }

    assert stages["retrieval"]["cost_usd"] == 0.0

    assert stages["generation"]["cost_usd"] > 0

    assert (
        stages["generation"]["input_tokens"]
        == 900
    )


def test_trace_totals_sum_its_spans():

    trace = Trace(
        trace_id="T1",
        question="q",
        prompt_version="v2",
        started_at="2025-11-04T14:37:00+00:00",
    )

    for _ in range(3):

        trace.spans.append(
            Span(
                name="generate",
                stage="generation",
                input_tokens=100,
                output_tokens=10,
            )
        )

    assert trace.input_tokens == 300

    assert trace.output_tokens == 30


# ---------------- the recorder --------------------


def test_the_recorder_writes_one_row(tmp_path):

    path = str(tmp_path / "requests.jsonl")

    with Recorder(
        "How many days of leave?",
        "v2",
        path=path,
    ) as trace:

        with trace.span(
            "retrieve",
            "retrieval",
        ):
            pass

        trace.answer = "Twenty-five days."

    rows = read_traces(path)

    assert len(rows) == 1

    assert (
        rows[0]["answer"] == "Twenty-five days."
    )

    assert rows[0]["prompt_version"] == "v2"


def test_both_input_and_output_are_indexed(
    tmp_path,
):
    """
    The drill turns on this. A complaint describes
    what the user SAW, so the answer has to be
    searchable, not just the question.
    """

    path = str(tmp_path / "requests.jsonl")

    with Recorder(
        "a question",
        "v2",
        path=path,
    ) as trace:

        trace.answer = "an answer"

    row = read_traces(path)[0]

    assert "question" in row

    assert "answer" in row


def test_context_ids_are_recorded(tmp_path):
    """
    Without these, a wrong answer cannot be split
    into "retrieval served the wrong passage" and
    "the model ignored the right one".
    """

    path = str(tmp_path / "requests.jsonl")

    with Recorder(
        "q",
        "v2",
        path=path,
    ) as trace:

        trace.context_ids = ["HR-202-2.4-abc"]

    row = read_traces(path)[0]

    assert row["context_ids"] == [
        "HR-202-2.4-abc"
    ]


def test_a_failing_request_is_still_logged(
    tmp_path,
):
    """
    A logged failure is still a failure - the
    recorder must not swallow the exception, and
    must not drop the row either.
    """

    path = str(tmp_path / "requests.jsonl")

    try:

        with Recorder(
            "q",
            "v2",
            path=path,
        ):
            raise ValueError("boom")

    except ValueError:
        pass

    rows = read_traces(path)

    assert len(rows) == 1

    assert "boom" in rows[0]["error"]


def test_a_span_records_its_error(tmp_path):

    path = str(tmp_path / "requests.jsonl")

    try:

        with Recorder(
            "q",
            "v2",
            path=path,
        ) as trace:

            with trace.span(
                "generate",
                "generation",
            ):
                raise RuntimeError("api down")

    except RuntimeError:
        pass

    row = read_traces(path)[0]

    assert (
        "api down" in row["spans"][0]["error"]
    )


def test_reading_a_missing_log_is_empty(
    tmp_path,
):

    assert (
        read_traces(
            str(tmp_path / "nope.jsonl")
        )
        == []
    )


# ---------------- prompt versioning ---------------


def test_every_shipped_version_resolves():
    """
    A trace from last Tuesday has to keep meaning
    what it meant last Tuesday, so no released
    version may be deleted.
    """

    for version in ("v1", "v2"):
        assert get_prompt(version)


def test_an_unknown_version_is_refused():

    try:
        get_prompt("v99")

    except ValueError as error:
        assert "v99" in str(error)

    else:
        raise AssertionError(
            "an unknown prompt version should "
            "raise"
        )


def test_v2_adds_the_on_topic_rule():
    """
    Compared on collapsed whitespace, because the
    rule wraps across lines in the source and a
    literal substring check would be asserting the
    line width rather than the content.
    """

    def flat(text: str) -> str:

        return " ".join(text.lower().split())

    rule = (
        "check that the retrieved context is "
        "about the subject the question asks "
        "about"
    )

    assert rule in flat(PROMPTS["v2"])

    assert rule not in flat(PROMPTS["v1"])

    # v2 is v1 plus one rule, not a rewrite, so the
    # before/after is attributable to that rule.
    assert len(PROMPTS["v2"]) > len(
        PROMPTS["v1"]
    )


def test_the_current_version_is_the_fixed_one():

    assert CURRENT_PROMPT_VERSION == "v2"


# ---------------- the topic gate ------------------


def test_the_incident_passage_does_not_cover_notice():
    """
    The exact trap from the drill. HR-202 2.4 says
    "where the notice given is shorter than this
    policy requires" - about booking annual leave.
    A bare keyword gate matches it and ships the
    wrong answer.
    """

    passage = (
        "All annual leave must be requested "
        "through the human resources system. A "
        "manager may decline a request where the "
        "notice given is shorter than this policy "
        "requires."
    )

    assert not covers_topic(
        passage,
        "notice_period",
    )


def test_a_real_notice_passage_does_cover_it():

    passage = (
        "An employee who wishes to resign must "
        "give written notice. The notice period "
        "is thirty days."
    )

    assert covers_topic(
        passage,
        "notice_period",
    )


def test_resignation_questions_are_gated():

    assert (
        question_topic(
            "What notice period do I need to "
            "give if I resign?"
        )
        == "notice_period"
    )


def test_a_bare_notice_question_is_not_gated():
    """
    E21 - notice given when a remote arrangement is
    withdrawn - is a real question this corpus
    answers. Gating on the word alone refused it.
    """

    assert (
        question_topic(
            "How much notice is given if a fully "
            "remote arrangement is withdrawn?"
        )
        is None
    )


def test_ordinary_questions_are_not_gated():

    for question in (
        "How many days of annual leave do I get?",
        "What are my working hours?",
        "How do I request annual leave?",
    ):

        assert (
            question_topic(question) is None
        ), question
