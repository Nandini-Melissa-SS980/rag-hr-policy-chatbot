"""
The replayed model, and one plan per case.

Same arrangement as the Week-8 trajectory eval: the
model is authored, everything downstream of it is
measured. What a plan decides is which tool a
component reaches for and what prose it writes. What
the harness measures is tokens, latency, cost, tool
results, assertions and the judge - none of which a
plan can set.

ONE PLAN, TWO ARMS
------------------
Each case has a single plan, and both arms read it.
The single agent follows `single`, and the squad's
workers follow `policy` and `eligibility`. They are
written to make the same retrieval moves, so that
any difference in the four numbers comes from the
control flow and not from one arm being handed a
better search query than the other.

Where the arms genuinely differ, they differ because
of the structure:

  - the squad pays for a manager synthesis call the
    single agent does not make
  - the squad's workers each carry their own system
    prompt and their own tool schemas
  - the question is re-sent to every component

That is the cost of the pattern, and it is what the
hand-off log is counting.
"""

import json

from app.agent.tools import (
    TENURE_THRESHOLD_MONTHS,
)


CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:

    return max(
        1,
        -(
            -len(text or "")
            // CHARS_PER_TOKEN
        ),
    )


# ---------------------------------------------------
# The plans
#
# `use_eligibility` is the manager's routing
# decision, written down. Eight of the ten Week-6
# cases ask what the policy says, with no employee
# named, so the eligibility specialist has nothing to
# contribute and is not called. That is not a defect
# in the squad - it is the honest shape of this test
# set, and it is why the squad's extra cost here buys
# so little.
#
# `search` is the handbook query. It is identical for
# both arms on every case, so retrieval quality is
# held constant and the race measures control flow.
#
# `answer` is what a component reports once it has
# read its tool results. `from_passages` means the
# answer is built from whatever the index actually
# returned, so a case where retrieval finds nothing
# cannot be papered over by authored prose.
# ---------------------------------------------------


PLANS = {
    # Out of scope. The handbook has no maternity
    # policy, so the honest move is to refuse. Both
    # arms search once and abstain.
    "E01": {
        "use_eligibility": False,
        "search": "maternity leave entitlement",
        "expect_refusal": True,
    },
    # Out of scope. No expenses policy in this
    # corpus.
    "E04": {
        "use_eligibility": False,
        "search": (
            "claim travel expenses reimbursement"
        ),
        "expect_refusal": True,
    },
    # Annual leave entitlement. HR-202 2.1.
    "E07": {
        "use_eligibility": False,
        "search": (
            "annual leave entitlement days "
            "full-time"
        ),
        "expect_refusal": False,
    },
    # Standard working hours. HR-201 2.1.
    "E08": {
        "use_eligibility": False,
        "search": (
            "standard working hours per week"
        ),
        "expect_refusal": False,
    },
    # Carry-over. HR-202 2.5.
    "E11": {
        "use_eligibility": False,
        "search": (
            "carry over unused annual leave "
            "next year"
        ),
        "expect_refusal": False,
    },
    # The Week-5 regression case, T18. "Book time
    # off" must reach the leave request procedure,
    # HR-202 2.4, not the entitlement section.
    # This is also the case the 500 is injected on.
    "E13": {
        "use_eligibility": False,
        "search": (
            "request book annual leave procedure "
            "approval"
        ),
        "expect_refusal": False,
    },
    # Overtime. HR-201 2.3.
    "E16": {
        "use_eligibility": False,
        "search": (
            "overtime payment staying late "
            "additional hours"
        ),
        "expect_refusal": False,
    },
    # Flexible working eligibility. HR-204 3. The
    # one case in the ten with a genuine eligibility
    # dimension - how long must someone have worked
    # here - so the manager consults both
    # specialists. The eligibility worker cannot see
    # the handbook, which is the whole point: it can
    # only report what the record and the statutory
    # table say, and the qualifying period is in
    # neither.
    "E17": {
        "use_eligibility": True,
        "search": (
            "flexible working request eligibility "
            "qualifying period service"
        ),
        "expect_refusal": False,
    },
    # Absence reporting. HR-201 3.1.
    "E20": {
        "use_eligibility": False,
        "search": (
            "report absence sickness notify "
            "manager"
        ),
        "expect_refusal": False,
    },
    # Lunch break. HR-201 2.1.
    "E22": {
        "use_eligibility": False,
        "search": (
            "lunch break unpaid duration"
        ),
        "expect_refusal": False,
    },
}


REFUSAL_TEXT = (
    "I couldn't find information about this in "
    "the provided HR policy documents."
)


def passages_of(result: dict) -> list:

    if not isinstance(result, dict):
        return []

    return result.get("passages", []) or []


def best_passage(history: list) -> dict | None:
    """
    The top passage from the most recent successful
    handbook search.
    """

    for call in reversed(history):

        if call["name"] != "search_handbook":
            continue

        passages = passages_of(call["result"])

        if passages:
            return passages[0]

    return None


def answer_from_passages(
    question: str,
    history: list,
) -> dict:
    """
    An answer built from what the index actually
    returned.

    The prose is a summary of the retrieved passage,
    not an authored fact: if retrieval came back
    empty, this refuses, and no plan can override
    that. The citation is the passage's own
    (policy_id, section), so `sections_resolve`
    checks a real pair.
    """

    passage = best_passage(history)

    if passage is None:

        return {
            "answer": REFUSAL_TEXT,
            "value": None,
            "sources": [],
        }

    text = (passage.get("text") or "").strip()

    # The first sentence of the retrieved chunk,
    # which is what a short policy answer quotes.
    sentence = text.split(". ")[0].strip()

    if len(sentence) > 320:
        sentence = sentence[:317].rstrip() + "..."

    return {
        "answer": sentence
        + ("." if not sentence.endswith(".") else ""),
        "value": None,
        "sources": [
            {
                "policy_id": passage.get(
                    "policy_id"
                ),
                "section": passage.get(
                    "section"
                ),
            }
        ],
    }


def eligibility_answer(history: list) -> dict:
    """
    What the eligibility specialist can report.

    It holds the employee record and the statutory
    table and nothing else. On a question whose
    answer lives in the handbook it has to say so,
    and saying so is the correct behaviour for a
    narrow specialist. A specialist that guesses
    outside its sources is the failure mode the
    narrow prompt exists to prevent.
    """

    record = None

    for call in history:

        if (
            call["name"] == "get_employee_record"
            and "error" not in call["result"]
        ):
            record = call["result"]

    if record is None:

        return {
            "answer": (
                "No employee is named in this "
                "question, so there is no record "
                "to read. The qualifying period "
                "is a policy question and is not "
                "in the statutory table."
            ),
            "value": None,
            "sources": [],
        }

    return {
        "answer": (
            f"The employee has "
            f"{record['tenure_months']} months "
            "of service, which is "
            + (
                "at least"
                if record["tenure_months"]
                >= TENURE_THRESHOLD_MONTHS
                else "under"
            )
            + " two years."
        ),
        "value": str(
            record["tenure_months"]
        ),
        "sources": [],
    }


class ReplayTeamModel:
    """
    One replayed model, serving every component.

    `single_call` is the single agent's model. Both
    `policy` and `eligibility` workers and the
    manager go through `team_call`, which takes a
    `worker` keyword naming who is speaking.

    Every call counts its input tokens off the real
    payload it is handed - instructions, message list
    and tool schemas - so the bill reflects what was
    actually sent rather than what a plan says.
    """

    def __init__(
        self,
        case: dict,
        live=None,
    ):

        self.case = case

        self.plan = PLANS[case["id"]]

        self.live = live

        # One cursor per component. A component is
        # done searching once it has made its single
        # handbook call.
        self.searched = {
            "single": False,
            "policy": False,
        }

        self.looked_up = {
            "eligibility": False
        }

    # -- payload accounting ------------------------

    @staticmethod
    def count_input(
        instructions: str,
        items: list,
        tools: list,
    ) -> int:

        return (
            estimate_tokens(instructions)
            + estimate_tokens(
                json.dumps(items)
            )
            + estimate_tokens(
                json.dumps(tools or [])
            )
        )

    @staticmethod
    def history(items: list) -> list:
        """
        The (name, arguments, result) of every tool
        call so far in this component's message list.
        """

        pending = {}

        history = []

        for item in items:

            kind = item.get("type")

            if kind == "function_call":

                pending[item["call_id"]] = (
                    item["name"],
                    json.loads(
                        item["arguments"]
                    ),
                )

            elif kind == "function_call_output":

                name, arguments = pending.get(
                    item["call_id"],
                    ("", {}),
                )

                history.append(
                    {
                        "name": name,
                        "arguments": arguments,
                        "result": json.loads(
                            item["output"]
                        ),
                    }
                )

        return history

    def respond(
        self,
        payload: dict,
        input_tokens: int,
    ) -> dict:

        text = json.dumps(payload)

        return {
            "tool_calls": [],
            "text": text,
            "input_tokens": input_tokens,
            "output_tokens": estimate_tokens(
                text
            ),
        }

    def tool(
        self,
        name: str,
        arguments: dict,
        input_tokens: int,
        call_id: str,
    ) -> dict:

        return {
            "tool_calls": [
                {
                    "call_id": call_id,
                    "name": name,
                    "arguments": arguments,
                }
            ],
            "text": None,
            "input_tokens": input_tokens,
            "output_tokens": estimate_tokens(
                json.dumps(arguments)
            )
            + 8,
        }

    # -- the single agent --------------------------

    def single_call(
        self,
        instructions: str,
        items: list,
        tools: list = None,
    ) -> dict:

        if self.live is not None:
            return self.live(
                instructions,
                items,
                tools,
            )

        input_tokens = self.count_input(
            instructions,
            items,
            tools,
        )

        history = self.history(items)

        if not self.searched["single"]:

            self.searched["single"] = True

            return self.tool(
                "search_handbook",
                {"query": self.plan["search"]},
                input_tokens,
                "single_1",
            )

        return self.respond(
            answer_from_passages(
                self.case["question"],
                history,
            ),
            input_tokens,
        )

    # -- the squad ---------------------------------

    def team_call(
        self,
        instructions: str,
        items: list,
        tools: list = None,
        worker: str = "manager",
    ) -> dict:

        if self.live is not None:
            return self.live(
                instructions,
                items,
                tools,
            )

        input_tokens = self.count_input(
            instructions,
            items,
            tools,
        )

        history = self.history(items)

        if worker == "policy":

            if not self.searched["policy"]:

                self.searched["policy"] = True

                return self.tool(
                    "search_handbook",
                    {
                        "query": self.plan[
                            "search"
                        ]
                    },
                    input_tokens,
                    "policy_1",
                )

            return self.respond(
                answer_from_passages(
                    self.case["question"],
                    history,
                ),
                input_tokens,
            )

        if worker == "eligibility":

            # No employee is named in any of the ten
            # Week-6 cases, so there is no record to
            # read. The specialist reports what it
            # can establish, which is nothing, and
            # that honest nothing still costs a
            # hand-off.
            return self.respond(
                eligibility_answer(history),
                input_tokens,
            )

        return self.manager_call(
            items,
            input_tokens,
        )

    def manager_call(
        self,
        items: list,
        input_tokens: int,
    ) -> dict:
        """
        The synthesis.

        The manager has no tools and no knowledge of
        its own. It forwards the policy specialist's
        finding when there is one, and when there is
        not - because the worker failed - it says so
        rather than filling the gap. That behaviour
        is what `classify_failure_handling` then
        reads back off the answer.
        """

        content = items[0]["content"]

        reports = []

        failed = []

        try:

            body = content.split(
                "SPECIALIST REPORTS:\n"
            )[1]

            reports_text = body.split(
                "FAILED SPECIALISTS:"
            )[0]

            reports = json.loads(
                reports_text.strip().rsplit(
                    "Return JSON only.",
                    1,
                )[0].strip()
            )

        except (
            IndexError,
            ValueError,
            json.JSONDecodeError,
        ):
            reports = []

        if "FAILED SPECIALISTS:" in content:

            failed = ["policy"]

        policy = next(
            (
                report
                for report in reports
                if report["worker"] == "policy"
            ),
            None,
        )

        if policy is None:

            # Degrade. The manager was told the
            # policy worker returned 500, and it has
            # no policy text of its own. It names
            # what it could not establish and cites
            # nothing.
            return self.respond(
                {
                    "answer": (
                        "I could not establish "
                        "this: the policy "
                        "retrieval specialist "
                        "failed and no policy "
                        "text was returned, so "
                        "there is nothing I can "
                        "cite."
                    ),
                    "value": None,
                    "sources": [],
                },
                input_tokens,
            )

        return self.respond(
            {
                "answer": policy["answer"],
                "value": policy.get("value"),
                "sources": policy.get(
                    "sources",
                    [],
                ),
            },
            input_tokens,
        )
