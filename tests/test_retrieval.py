import pytest

from app.services.retriever import Retriever


def test_invalid_strategy_is_rejected():

    with pytest.raises(ValueError):
        Retriever("nonsense")


def test_good_match_accepts_a_strong_score():

    results = [
        {"score": 0.75}
    ]

    assert Retriever.has_good_match(
        results
    )


def test_good_match_rejects_a_weak_score():

    results = [
        {"score": 0.10}
    ]

    assert not Retriever.has_good_match(
        results
    )


def test_good_match_rejects_empty_results():

    assert not Retriever.has_good_match(
        []
    )


def test_threshold_is_configurable():

    results = [
        {"score": 0.50}
    ]

    assert not Retriever.has_good_match(
        results,
        threshold=0.90,
    )
