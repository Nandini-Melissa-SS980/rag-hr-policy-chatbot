"""
The same task as a fixed workflow.

Three hard-coded steps, the same three tools, the
same model, the same output contract as the agent.
There is no loop: the model is called exactly once,
at the end, to phrase the answer. It never chooses a
tool.

The branch on tenure is a plain `if` here. That is
the whole comparison - the agent decides the path at
run time, this decides it at authoring time.
"""

import json
import re
import time

from app.agent.loop import (
    Usage,
    Trace,
    parse_final,
)
from app.agent.tools import (
    JURISDICTIONS,
    TENURE_THRESHOLD_MONTHS,
    get_employee_record,
    get_jurisdiction_rules,
    search_handbook,
)


SYSTEM_PROMPT = """
You phrase an answer to an HR entitlement question.

Everything you need has already been gathered. Do
not ask for more information and do not speculate
beyond what is given.

Reply with JSON only:

{
  "answer": "one or two sentences",
  "value": "the single key figure, digits only where
            it is a number of days",
  "sources": [{"policy_id": "HR-201", "section": "3.1"}]
}

Use "value": null if the question has no single
figure.
"""

EMPLOYEE_ID = re.compile(
    r"E-\d{4}",
    re.IGNORECASE,
)


def find_employee_id(
    question: str,
) -> str | None:

    match = EMPLOYEE_ID.search(question)

    if match:
        return match.group(0).upper()

    return None


def find_jurisdiction(
    question: str,
) -> str | None:
    """
    For questions that name a region instead of an
    employee, such as a statutory minimum.
    """

    lowered = question.lower()

    for jurisdiction in JURISDICTIONS:

        if jurisdiction.lower() in lowered:
            return jurisdiction

    return None


def run_workflow(
    question: str,
    model_call,
) -> dict:

    usage = Usage()

    trace = Trace()

    started = time.monotonic()

    # ---- Step 1: the employee ----------------
    # Three authored branches, because three shapes
    # of question turn up in the input set. Each new
    # shape needs another branch written by hand -
    # which is the cost the race is measuring.
    employee_id = find_employee_id(question)

    named_jurisdiction = find_jurisdiction(
        question
    )

    record = {}

    if employee_id is not None:

        branch = "employee"

        record = get_employee_record(
            employee_id
        )

    elif named_jurisdiction is not None:

        branch = "jurisdiction"

    else:
        branch = "handbook_only"

    trace.add(
        "step_1",
        f"branch={branch} "
        f"record={json.dumps(record)[:100]}",
    )

    # ---- Step 2: the policy text -------------
    passages = search_handbook(question)

    trace.add(
        "step_2",
        f"search_handbook -> "
        f"{len(passages['passages'])} passage(s)",
    )

    # ---- Step 3: the statutory table ---------
    # The branch the agent would have to reason
    # its way to is written out here.
    rules = {}

    applicable_notice_days = None

    jurisdiction = record.get(
        "jurisdiction",
        named_jurisdiction,
    )

    if jurisdiction:

        rules = get_jurisdiction_rules(
            jurisdiction
        )

        if (
            "error" not in rules
            and "tenure_months" in record
        ):

            under_two_years = (
                record["tenure_months"]
                < TENURE_THRESHOLD_MONTHS
            )

            applicable_notice_days = (
                rules[
                    "notice_days_under_2_years"
                ]
                if under_two_years
                else rules[
                    "notice_days_2_years_or_more"
                ]
            )

    trace.add(
        "step_3",
        f"get_jurisdiction_rules("
        f"{jurisdiction}) -> applicable notice "
        f"{applicable_notice_days} day(s)",
    )

    # ---- One model call to phrase it ---------
    facts = {
        "question": question,
        "employee": record,
        "jurisdiction_rules": rules,
        "applicable_notice_days": (
            applicable_notice_days
        ),
        "policy_passages": passages[
            "passages"
        ],
    }

    response = model_call(
        SYSTEM_PROMPT,
        [
            {
                "role": "user",
                "content": (
                    "FACTS:\n"
                    f"{json.dumps(facts, indent=2)}"
                    "\n\nReturn JSON only."
                ),
            }
        ],
        None,
    )

    usage.add(
        response.get("input_tokens", 0),
        response.get("output_tokens", 0),
    )

    trace.add(
        "phrase",
        "single model call, no tools offered",
    )

    final = parse_final(
        response.get("text")
    )

    return {
        "system": "workflow",
        "question": question,
        "answer": final["answer"],
        "value": final["value"],
        "sources": final["sources"],
        "iterations": 1,
        "terminated_by": None,
        "usage": usage.as_dict(),
        "seconds": round(
            time.monotonic() - started,
            3,
        ),
        "steps": trace.steps,
        "log": trace.lines(),
    }
