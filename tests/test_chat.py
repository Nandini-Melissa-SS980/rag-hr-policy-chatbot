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
