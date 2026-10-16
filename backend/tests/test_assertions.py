from evaluation.assertions import (
    all_passed,
    refusal_is_correct,
    run_assertions,
    sections_resolve,
    sources_present,
)


VALID = {
    ("HR-202", "2.1"),
    ("HR-204", "6"),
}


def passed(result: tuple) -> bool:

    return result[0]


def test_sources_present_accepts_a_citation():

    assert passed(
        sources_present(
            [{"policy_id": "HR-202"}]
        )
    )


def test_sources_present_rejects_an_empty_list():

    assert not passed(
        sources_present([])
    )


def test_sections_resolve_accepts_a_real_section():

    assert passed(
        sections_resolve(
            [
                {
                    "policy_id": "HR-202",
                    "section": "2.1",
                }
            ],
            VALID,
        )
    )


def test_sections_resolve_rejects_an_invented_section():
    """
    The failure this catches: a citation to a
    section that was never in the documents.
    """

    result = sections_resolve(
        [
            {
                "policy_id": "HR-202",
                "section": "9.9",
            }
        ],
        VALID,
    )

    assert not passed(result)
    assert "HR-202/9.9" in result[1]


def test_sections_resolve_reports_every_bad_section():

    result = sections_resolve(
        [
            {
                "policy_id": "HR-202",
                "section": "2.1",
            },
            {
                "policy_id": "HR-999",
                "section": "1",
            },
        ],
        VALID,
    )

    assert not passed(result)
    assert "HR-999/1" in result[1]


def test_refusal_is_correct_when_it_refuses_out_of_scope():

    assert passed(
        refusal_is_correct(
            abstained=True,
            expect_refusal=True,
        )
    )


def test_answering_an_uncovered_question_fails():

    result = refusal_is_correct(
        abstained=False,
        expect_refusal=True,
    )

    assert not passed(result)
    assert "do not cover" in result[1]


def test_refusing_a_covered_question_fails():

    assert not passed(
        refusal_is_correct(
            abstained=True,
            expect_refusal=False,
        )
    )


def test_a_refused_case_is_not_asked_for_citations():
    """
    A refusal has no sources, so the citation
    assertions would fail it for the wrong reason.
    """

    results = run_assertions(
        {"expect_refusal": True},
        abstained=True,
        sources=[],
        valid_sections=VALID,
    )

    assert list(results) == [
        "refusal_is_correct"
    ]

    assert all_passed(results)


def test_an_answered_case_runs_every_assertion():

    results = run_assertions(
        {"expect_refusal": False},
        abstained=False,
        sources=[
            {
                "policy_id": "HR-204",
                "section": "6",
            }
        ],
        valid_sections=VALID,
    )

    assert sorted(results) == [
        "refusal_is_correct",
        "sections_resolve",
        "sources_present",
    ]

    assert all_passed(results)


def test_all_passed_is_false_when_one_fails():

    results = run_assertions(
        {"expect_refusal": False},
        abstained=False,
        sources=[],
        valid_sections=VALID,
    )

    assert not all_passed(results)
