"""
The LangSmith exporter.

What matters here is not that runs reach the dashboard - that
is checked by running it with a key - but that the exporter
cannot harm the request path. It is off by default, it
swallows its own failures, and the JSONL row is written
whether it works or not.
"""

import uuid

import app.langsmith_export as langsmith_export
from app.langsmith_export import (
    _delta,
    _documents,
    _parse_time,
    _run_type,
    export_trace,
    get_client,
)
from app.observability import Recorder, read_traces


# ---------------- off by default ------------------


def test_disabled_unless_asked(monkeypatch):
    """
    A client that cannot reach the service must never slow a
    request down, so the default is off.
    """

    monkeypatch.setattr(
        langsmith_export,
        "LANGSMITH_ENABLED",
        False,
    )

    monkeypatch.setattr(
        langsmith_export,
        "_client",
        None,
    )

    monkeypatch.setattr(
        langsmith_export,
        "_failed",
        False,
    )

    assert get_client() is None

    assert export_trace({"trace_id": "T1"}) is False


def test_a_missing_key_is_reported_once(
    monkeypatch,
):
    """
    Reported once, not once per request.
    """

    monkeypatch.setattr(
        langsmith_export,
        "LANGSMITH_ENABLED",
        True,
    )

    monkeypatch.setattr(
        langsmith_export,
        "_client",
        None,
    )

    monkeypatch.setattr(
        langsmith_export,
        "_failed",
        False,
    )

    monkeypatch.delenv(
        "LANGSMITH_API_KEY",
        raising=False,
    )

    assert get_client() is None

    # The second call must not retry: _failed is sticky.
    assert langsmith_export._failed is True
    assert get_client() is None


def test_an_export_failure_never_raises(
    monkeypatch,
):

    class Boom:
        def __getattr__(self, name):
            raise RuntimeError("service gone")

    monkeypatch.setattr(
        langsmith_export,
        "LANGSMITH_ENABLED",
        True,
    )

    monkeypatch.setattr(
        langsmith_export,
        "_client",
        Boom(),
    )

    monkeypatch.setattr(
        langsmith_export,
        "_failed",
        False,
    )

    assert (
        export_trace({"trace_id": "T1"}) is False
    )


def test_the_log_is_written_even_if_export_fails(
    tmp_path,
    monkeypatch,
):
    """
    The JSONL file is the source of truth. A dashboard being
    down must never cost us the row the drill greps.
    """

    monkeypatch.setattr(
        langsmith_export,
        "LANGSMITH_ENABLED",
        True,
    )

    def explode(payload):
        raise RuntimeError("service gone")

    monkeypatch.setattr(
        langsmith_export,
        "export_trace",
        explode,
    )

    path = str(tmp_path / "requests.jsonl")

    with Recorder(
        "How much leave?",
        "v2",
        path=path,
    ) as trace:

        trace.answer = "Twenty-five days."

    rows = read_traces(path)

    assert len(rows) == 1
    assert rows[0]["answer"] == "Twenty-five days."


# ---------------- the translation -----------------


def test_stages_map_to_langsmith_run_types():
    """
    The run type is what makes LangSmith render retrieved
    chunks as documents and tokens as a cost column, rather
    than as anonymous key-value pairs on a generic run.
    """

    assert _run_type("retrieval") == "retriever"
    assert _run_type("generation") == "llm"
    assert _run_type("tools") == "tool"
    assert _run_type("anything else") == "chain"


def test_documents_carry_text_and_metadata():

    documents = _documents(
        [
            {
                "chunk_id": "HR-202-2.1-abc",
                "score": 0.87,
                "text": "Full-time employees receive twenty-five days.",
                "policy_id": "HR-202",
                "section": "2.1",
            }
        ]
    )

    assert len(documents) == 1

    assert (
        "twenty-five"
        in documents[0]["page_content"]
    )

    metadata = documents[0]["metadata"]

    assert metadata["policy_id"] == "HR-202"
    assert metadata["section"] == "2.1"
    assert metadata["score"] == 0.87


def test_a_missing_timestamp_is_not_fatal():

    assert _parse_time("not a date") is not None

    parsed = _parse_time(
        "2025-11-04T14:37:00+00:00"
    )

    assert parsed.year == 2025


def test_a_negative_duration_is_clamped():

    assert _delta(-5).total_seconds() == 0.0


def test_the_run_tree_has_the_right_shape(
    monkeypatch,
):
    """
    One chain root, a retriever child carrying the passages,
    and an llm child carrying the token counts.
    """

    from langsmith import Client
    from langsmith.run_trees import RunTree

    client = Client(
        api_key="ls__not_used",
        api_url="https://api.smith.langchain.com",
    )

    started = _parse_time(
        "2025-11-04T14:37:00+00:00"
    )

    root = RunTree(
        id=uuid.uuid4(),
        name="hr360.request",
        run_type="chain",
        project_name="test",
        inputs={"question": "How much leave?"},
        outputs={"answer": "Twenty-five days."},
        start_time=started,
        extra={
            "metadata": {"prompt_version": "v2"}
        },
        client=client,
    )

    context = [
        {
            "chunk_id": "c1",
            "text": "Full-time employees receive twenty-five days.",
            "score": 0.87,
            "policy_id": "HR-202",
            "section": "2.1",
        }
    ]

    langsmith_export._add_child(
        root,
        {
            "name": "retrieve",
            "stage": "retrieval",
            "duration_ms": 15.0,
        },
        context,
        started,
    )

    langsmith_export._add_child(
        root,
        {
            "name": "generate",
            "stage": "generation",
            "duration_ms": 800.0,
            "input_tokens": 942,
            "output_tokens": 32,
            "total_tokens": 974,
        },
        context,
        started,
    )

    kinds = [
        child.run_type
        for child in root.child_runs
    ]

    assert kinds == ["retriever", "llm"]

    retriever = root.child_runs[0]

    assert (
        len(retriever.outputs["documents"]) == 1
    )

    generation = root.child_runs[1]

    usage = generation.outputs[
        "usage_metadata"
    ]

    assert usage["input_tokens"] == 942
    assert usage["total_tokens"] == 974


# ---------------- the trace carries the drill -----


def test_context_includes_the_passage_text():
    """
    Without the text a trace says WHICH chunk was served but
    not what it said, so telling "retrieval served the wrong
    passage" from "the model ignored the right one" needs a
    second lookup. The retriever view is built on this.
    """

    from app.services.answering import (
        describe_context,
    )

    described = describe_context(
        [
            {
                "chunk_id": "c1",
                "text": "Full-time employees receive twenty-five days.",
                "score": 0.87,
                "metadata": {
                    "policy_id": "HR-202",
                    "section": "2.1",
                },
            }
        ]
    )

    assert "twenty-five" in described[0]["text"]
