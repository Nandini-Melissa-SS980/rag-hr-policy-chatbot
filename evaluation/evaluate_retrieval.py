import json

from app.services.retriever import Retriever


def load_questions():

    with open(
        "evaluation/questions.json",
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


def evaluate_strategy(
    strategy: str,
    questions: list[dict],
):

    retriever = Retriever(
        strategy
    )

    results = []

    hits = 0

    for question in questions:

        retrieved = retriever.retrieve(
            question["question"],
            top_k=5,
        )

        expected = question[
            "expected"
        ]

        hit = any(
            result["metadata"].get(
                "policy_id"
            )
            == expected["policy_id"]
            and result["metadata"].get(
                "section"
            )
            == expected["section"]
            for result in retrieved
        )

        if hit:
            hits += 1

        results.append(
            {
                "question_id": question[
                    "id"
                ],
                "question": question[
                    "question"
                ],
                "expected": expected,
                "hit_in_top_5": hit,
                "results": retrieved,
            }
        )

    return hits, results


def main():

    questions = load_questions()

    all_results = {}

    for strategy in [
        "basic",
        "structure_aware",
    ]:

        hits, results = (
            evaluate_strategy(
                strategy,
                questions,
            )
        )

        print(
            f"{strategy}: "
            f"{hits}/{len(questions)}"
        )

        all_results[
            strategy
        ] = {
            "hits": hits,
            "total": len(questions),
            "results": results,
        }

    with open(
        "evaluation/retrieval_results.json",
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            all_results,
            file,
            indent=2,
        )


if __name__ == "__main__":
    main()