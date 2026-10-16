"""
Is the retrieved context about the subject that was
asked about?

This is rule 4 of prompt v2, written as a function so
the suite can be scored without a model while the key
is unfunded. Under `--live` the model applies the same
rule from the prompt text; this is the offline
equivalent, and it is deliberately narrow.

The topics listed are the ones this corpus does NOT
cover but gets asked about anyway - which is exactly
the set that produces confident wrong answers,
because the retriever always returns its closest
chunks and they score around 0.7 regardless.

A topic is "covered" if a passage actually uses its
vocabulary. Nothing clever: the failure being guarded
against is a passage about annual leave answering a
question about resignation, and a word check catches
that.
"""

import re


WORD = re.compile(r"[a-z0-9]+")


# question terms -> terms a passage must contain to
# count as covering that topic.
TOPICS = {
    # "notice" alone is not enough to say a passage
    # covers notice periods, and this is the exact
    # trap that caused the incident: HR-202 2.4 is
    # about requesting annual leave and contains the
    # phrase "where the notice given is shorter than
    # this policy requires". A bare keyword gate
    # matches it and lets the wrong answer through.
    #
    # So the word has to appear with the subject:
    # notice OF something - resigning, terminating,
    # leaving employment. `covered` holds the terms
    # that mean employment is ending, and a passage
    # has to use one of them.
    # `asked` deliberately excludes a bare "notice".
    # E21 - "how much notice is given if a fully
    # remote arrangement is withdrawn" - is a real
    # question this corpus answers in HR-207 4.2.
    # Gating on the word alone refused it, which the
    # suite caught on the first full run. The topic
    # is notice of LEAVING, so the question has to
    # say so.
    "notice_period": {
        "asked": {
            "resign",
            "resigning",
            "resignation",
            "quit",
            "quitting",
            "terminate",
            "termination",
        },
        "covered": {
            "resign",
            "resignation",
            "resigning",
            "termination",
            "terminate",
            "dismissal",
            "notice period",
        },
    },
    "redundancy": {
        "asked": {"redundancy", "redundant", "layoff"},
        "covered": {"redundancy", "redundant"},
    },
    "maternity": {
        "asked": {
            "maternity",
            "paternity",
            "parental",
        },
        "covered": {
            "maternity",
            "paternity",
            "parental",
        },
    },
    "pension": {
        "asked": {"pension", "pensions"},
        "covered": {"pension", "pensions"},
    },
}


def words(text: str) -> set:

    return set(
        WORD.findall((text or "").lower())
    )


def question_topic(
    question: str,
) -> str | None:
    """
    The topic a question is about, or None when it is
    not one of the tracked ones.

    None means "no topic gate applies", so an ordinary
    leave or hours question is unaffected by this
    rule. That is what keeps E30 green: the fix must
    not make the app refuse things it can answer.
    """

    asked = words(question)

    for topic, terms in TOPICS.items():

        if asked & terms["asked"]:
            return topic

    return None


def covers_topic(
    text: str,
    topic: str,
) -> bool:
    """
    Whether a passage actually covers the topic.

    Entries containing a space are matched as
    phrases, so "notice period" requires the two
    words together. That distinction is the whole
    fix: the passage that caused the incident
    contains "notice" but never "notice period",
    because it is about booking annual leave.
    """

    if topic not in TOPICS:
        return True

    lowered = (text or "").lower()

    present = words(text)

    for term in TOPICS[topic]["covered"]:

        if " " in term:

            if term in lowered:
                return True

        elif term in present:
            return True

    return False
