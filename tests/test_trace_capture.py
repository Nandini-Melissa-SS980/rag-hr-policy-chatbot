from evaluation.trace_capture import (
    describe_retrieved,
    sample_questions,
)


POOL = [
    {
        "id": f"P{index}",
        "question": f"question {index}",
    }
    for index in range(1, 31)
]


def ids(questions: list[dict]) -> list[str]:

    return [
        question["id"]
        for question in questions
    ]


def test_sample_is_the_requested_size():

    assert (
        len(
            sample_questions(
                POOL,
                size=20,
            )
        )
        == 20
    )


def test_sample_is_reproducible():
    """
    A fixed seed is what makes a trace batch
    re-runnable by someone else.
    """

    first = sample_questions(
        POOL,
        size=10,
        seed=42,
    )

    second = sample_questions(
        POOL,
        size=10,
        seed=42,
    )

    assert ids(first) == ids(second)


def test_a_different_seed_samples_differently():

    first = sample_questions(
        POOL,
        size=10,
        seed=42,
    )

    second = sample_questions(
        POOL,
        size=10,
        seed=7,
    )

    assert ids(first) != ids(second)


def test_sample_does_not_repeat_a_question():

    sampled = ids(
        sample_questions(
            POOL,
            size=20,
        )
    )

    assert len(set(sampled)) == 20


def test_describe_retrieved_numbers_the_ranks():

    results = [
        {
            "chunk_id": "a",
            "text": "first",
            "score": 0.9,
            "metadata": {
                "policy_id": "HR-202",
                "section": "2.1",
                "source_file": "HR-202.pdf",
            },
        },
        {
            "chunk_id": "b",
            "text": "second",
            "score": 0.8,
            "metadata": {},
        },
    ]

    described = describe_retrieved(
        results
    )

    assert [
        item["rank"] for item in described
    ] == [1, 2]

    assert described[0]["policy_id"] == "HR-202"

    # Missing metadata must not crash a capture.
    assert described[1]["policy_id"] == ""


def test_describe_retrieved_keeps_the_full_text():
    """
    A trace has to be replayable, so the chunk
    text is stored whole rather than previewed.
    """

    text = "word " * 400

    described = describe_retrieved(
        [
            {
                "chunk_id": "a",
                "text": text,
                "score": 0.5,
                "metadata": {},
            }
        ]
    )

    assert described[0]["text"] == text
