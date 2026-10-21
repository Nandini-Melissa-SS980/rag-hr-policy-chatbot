"""
Is this question about something the corpus covers?

THE PROBLEM A THRESHOLD CANNOT SOLVE
------------------------------------
Measured on the desk index, the top retrieval score for a
question this corpus answers runs 0.718-0.885. For one it does
not, 0.552-0.773. Those ranges overlap, so no threshold
separates them: "what is my salary band" scores 0.773 against
an annual-leave clause and clears any cut that still lets
"what notice do I give" through at 0.718.

The embedding is not wrong. Leave, salary and pension are all
HR-employment language and genuinely sit near each other; a
small focused corpus makes it worse, because with 28 chunks
there is always something at ~0.6.

So relevance is checked on subject, not on distance. A
question naming a topic the corpus does not cover is refused
before the score is consulted at all.

WHY A DENY LIST AND NOT AN ALLOW LIST
-------------------------------------
An allow list would refuse every question phrased in words
nobody anticipated, which is most of them. The list below
names the subjects this corpus is KNOWN not to cover - each
one a real question an HR team receives - and everything else
falls through to the retrieval gate as before.

That makes the list a maintenance item, and it is the right
one to maintain: adding a pensions policy means deleting a
line here, and the eval case that pins the refusal turns red
to tell you.
"""

import re


# Subjects the desk corpus does not cover. Each entry is a
# topic and the words that name it. A question matching one is
# refused regardless of what retrieval returns.
#
# `salary` is here twice over: there is no pay policy, AND the
# grade matrix explicitly says salary band data is not
# published to this system. Answering it from the grade the
# record just resolved would be a leak, not a lookup.
UNCOVERED = {
    "pension": (
        r"\bpension|retirement\s+(?:plan|scheme|"
        r"contribution)|superannuation|\b401k\b|"
        r"provident\s+fund\b"
    ),
    "salary": (
        r"\bsalary|\bpay\s*(?:rise|raise|scale|band|"
        r"grade)|\bcompensation\b|\bbonus\b|"
        r"\bremuneration\b|how much (?:do|am) I (?:get )?paid\b"
    ),
    "expenses": (
        r"\bexpense|reimburse|mileage\b|per\s*diem\b"
    ),
    "medical_cover": (
        r"private\s+(?:medical|health)|health\s+"
        r"insurance|\bdental\b|\bvision\s+cover"
    ),
    "training_budget": (
        r"training\s+budget|learning\s+budget|"
        r"tuition\s+(?:fee|reimbursement)"
    ),
    "equipment": (
        r"\blaptop\b|\bmonitor\b|desk\s+allowance|"
        r"home\s+office\s+(?:allowance|equipment)"
    ),
}


COMPILED = {
    topic: re.compile(pattern, re.IGNORECASE)
    for topic, pattern in UNCOVERED.items()
}


def uncovered_topic(question: str) -> str | None:
    """
    The uncovered subject this question is about, or None.

    None does not mean "covered" - it means this gate has no
    opinion and the retrieval score decides, which is the
    Week-6 behaviour.
    """

    for topic, pattern in COMPILED.items():

        if pattern.search(question):
            return topic

    return None


# What the refusal says. Named per topic so the answer tells
# the employee where to go instead, which is the difference
# between a refusal and a dead end.
REFERRALS = {
    "pension": (
        "Pension and retirement questions are not "
        "covered by the policies I hold."
    ),
    "salary": (
        "I do not hold pay or salary band data, and "
        "the grade band matrix states that salary "
        "information is not published to this system."
    ),
    "expenses": (
        "Expenses and reimbursement are not covered "
        "by the policies I hold."
    ),
    "medical_cover": (
        "Private medical cover is not covered by the "
        "policies I hold."
    ),
    "training_budget": (
        "Training and learning budgets are not "
        "covered by the policies I hold."
    ),
    "equipment": (
        "Equipment and home office allowances are "
        "not covered by the policies I hold."
    ),
}


def refusal_for(topic: str) -> str:

    return (
        f"{REFERRALS.get(topic, 'That is not covered by the policies I hold.')} "
        "Please ask an HR business partner."
    )
