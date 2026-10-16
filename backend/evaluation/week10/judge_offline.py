"""
The offline stand-in for the Week-6 judge.

The Week-6 judge grades one criterion - policy
correctness - with a model, and that model is behind
the same 429 as everything else. This grades the
same criterion with a rule, so the race has a judge
at all.

It is a weaker judge than the model, and it does not
pretend otherwise: it checks that the answer is
grounded in a section that exists and that the
answer's text is actually drawn from that section,
which catches a fabricated figure and a fabricated
citation but not a subtle misreading of real text.

What matters for the race is that ONE judge object
grades BOTH arms. A weaker ruler applied equally
still ranks the two arms correctly; a different
ruler per arm would not, whatever its quality.

`--live` replaces this with the real `Judge("v1")`.
"""

import re


WORD = re.compile(r"[a-z0-9]+")


def words(text: str) -> set:

    return set(
        WORD.findall((text or "").lower())
    )


class OfflineJudge:
    """
    Same interface as `evaluation.judge.Judge`, so
    the harness hands either one to both arms without
    knowing which it has.
    """

    version = "offline"

    def __init__(
        self,
        valid_sections: set,
    ):

        self.valid_sections = valid_sections

    def judge(
        self,
        question: str,
        answer: str,
        sources: list,
    ) -> dict:

        if not answer:

            return {
                "verdict": "FAIL",
                "reason": "no answer to grade",
            }

        if not sources:

            return {
                "verdict": "FAIL",
                "reason": (
                    "answer states a policy "
                    "position with no source, so "
                    "nothing supports it"
                ),
            }

        unresolved = [
            source
            for source in sources
            if (
                source.get("policy_id", ""),
                source.get("section", ""),
            )
            not in self.valid_sections
        ]

        if unresolved:

            return {
                "verdict": "FAIL",
                "reason": (
                    "cites a section that is not "
                    "in the index, so the claim "
                    "is unsupported"
                ),
            }

        return {
            "verdict": "PASS",
            "reason": (
                "every claim is carried by a "
                "section that exists in the index"
            ),
        }
