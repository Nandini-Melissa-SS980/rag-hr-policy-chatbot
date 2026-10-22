from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():

    response = client.get(
        "/api/health"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_stats_reports_a_count():

    response = client.get(
        "/api/stats"
    )

    assert response.status_code == 200
    assert response.json()["count"] > 0


def test_search_returns_scored_chunks():

    response = client.post(
        "/api/search",
        json={
            "question": "How much annual leave do I get?"
        },
    )

    results = response.json()

    assert response.status_code == 200
    assert results

    for result in results:
        assert result["chunk_id"]
        assert 0 <= result["score"] <= 1
        assert result["metadata"]["source_file"]


def test_search_validates_an_empty_question():

    response = client.post(
        "/api/search",
        json={"question": ""},
    )

    assert response.status_code == 422


def test_unknown_region_returns_nothing():
    """Documents the region bug: every chunk is stored as 'unknown'."""

    response = client.post(
        "/api/search",
        json={
            "question": "How much annual leave do I get?",
            "region": "India",
        },
    )

    assert response.json() == []
def test_metrics_projects_the_trace():
    """
    The UI number and the logged number come from one place.
    A second measurement would let them drift, and then
    "what did this question cost" has two answers.
    """

    from app.api.chat import metrics_from

    trace = {
        "trace_id": "R-abc123",
        "model": "gemini-3.8-flash",
        "prompt_version": "v2",
        "duration_ms": 1234.5,
        "total_tokens": 505,
        "cost_usd": 0.000286,
        "cost_by_stage": {
            "retrieval": {
                "duration_ms": 341.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
            },
            "generation": {
                "duration_ms": 890.0,
                "input_tokens": 425,
                "output_tokens": 80,
                "cost_usd": 0.000286,
            },
        },
        "labels": {
            "context": [
                {"score": 0.8706},
                {"score": 0.8094},
            ]
        },
    }

    metrics = metrics_from(trace)

    assert metrics.trace_id == "R-abc123"
    assert metrics.top_score == 0.8706
    assert metrics.retrieved == 2
    assert metrics.total_tokens == 505

    # Retrieval costs latency and no money; generation costs
    # both. The split is the actionable part.
    assert (
        metrics.stages["retrieval"].cost_usd == 0.0
    )
    assert (
        metrics.stages["generation"].cost_usd
        == 0.000286
    )


def test_metrics_survive_a_trace_with_no_context():
    """
    A refused question has no retrieved chunks. Reporting a
    top score of 0 is correct; raising is not.
    """

    from app.api.chat import metrics_from

    metrics = metrics_from(
        {"trace_id": "R-x", "labels": {}}
    )

    assert metrics.top_score == 0.0
    assert metrics.retrieved == 0
    assert metrics.stages == {}
