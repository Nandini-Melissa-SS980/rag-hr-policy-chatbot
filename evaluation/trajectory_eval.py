"""
Trajectory evaluation for the HR agent.

    python -m evaluation.trajectory_eval
    python -m evaluation.trajectory_eval --live

Week 8 - M4. The outcome eval asks whether the final
figure was right. This asks whether the agent earned
it: which tools it called, in what order, with which
arguments, how many steps it spent, and what the run
cost. A right notice period reached without ever
reading the employee's tenure passes the outcome eval
and is the failure this file exists to find.

Two arms, run in one process:

    baseline   the Week-7 tools, unchanged
    validated  one change - get_jurisdiction_rules
               requires the tenure the caller claims
               to know

One process and one harness, because a before number
and an after number measured by two different rulers
are not a comparison.

WHERE THE TRAJECTORIES COME FROM - READ THIS FIRST
--------------------------------------------------
The OpenAI account behind this project returns
429 insufficient_quota. It is the same block recorded
in results.md (Week 4) and error_analysis.md
(Week 5), and it is why every row in
race_results.json is a zero. So the ten plans in
PLANS are **authored**: they are paths this prompt
and this tool set make available, written down, not
API transcripts. Each one names the mechanism it is
modelling.

What is authored is the mistake. Everything after it
is computed, and that is the part being delivered:

  - the loop is app.agent.loop.run_agent, untouched,
    with its Week-7 budgets at their Week-7 values
  - the tools are the real tools, over the real
    fixture and the real policy index
  - the mitigated arm's extra steps are produced by
    the replayed model repairing a refused call, not
    written into any plan
  - the answer to a notice question is derived from
    what the run actually read, so a run that never
    read the record can only guess, and a run that
    did read it cannot
  - tokens are counted from the payload the loop
    really sends on each lap, so a run that loops
    pays for looping
  - every number in the tables is measured off those
    runs

--live swaps the replayed model for the real one and
scores identically, the moment the key is funded.
"""

import argparse
import json
import re
import statistics

from app.agent.loop import (
    Budgets,
    run_agent,
)
from app.agent.tools import (
    JURISDICTIONS,
    TENURE_THRESHOLD_MONTHS,
    build_toolset,
    load_fixture,
)
from app.config import (
    INPUT_COST_PER_1M,
    OPENAI_MODEL,
    OUTPUT_COST_PER_1M,
)
from evaluation.frozen_index import (
    build_handbook,
    valid_sections,
)
from evaluation.race import value_matches


QUESTIONS_PATH = (
    "evaluation/race_questions.json"
)

RESULTS_PATH = (
    "evaluation/trajectory_results.json"
)

# The usual rough conversion. It is an estimate, and
# it is the same estimate on both arms, which is what
# a before-and-after needs it to be.
CHARS_PER_TOKEN = 4


# ---------------------------------------------------
# 1. The expected sequences
# ---------------------------------------------------


def interleavings(
    core: tuple,
    optional: tuple,
) -> set:
    """
    Every sequence that keeps `core` in order and may
    or may not contain each optional tool, once, at
    any position.

    This is here so that a case with a legitimate
    second path is asserted as a set rather than as
    one sequence. Asserting a single order when two
    orders are both correct builds an eval that marks
    correct runs as failures and inflates the gap it
    is meant to measure.
    """

    paths = {tuple(core)}

    for tool in optional:

        grown = set()

        for path in paths:

            for index in range(len(path) + 1):

                grown.add(
                    path[:index]
                    + (tool,)
                    + path[index:]
                )

        paths |= grown

    return paths


# The dependency that makes this domain interesting:
# the statutory table holds two notice figures and
# only the employee's tenure says which one applies.
# So the record has to be read before the table, and
# a run that reads them the other way round decided
# the answer before it had the fact.
NOTICE_CORE = (
    "get_employee_record",
    "get_jurisdiction_rules",
)

NOTICE_OPTIONAL = ("search_handbook",)

NOTICE_MULTI_PATH_REASON = (
    "Checking whether the company has its own notice "
    "clause before falling back on the statutory "
    "table is a legitimate first move, and it is "
    "equally legitimate after the record or after "
    "the table. Four sequences are correct here, so "
    "four are accepted. The one thing that is not "
    "optional is the order of the two that matter: "
    "record before table."
)


CASES = [
    {
        "id": "R01",
        "employee_id": "E-1002",
        "core": NOTICE_CORE,
        "optional": NOTICE_OPTIONAL,
        "dependency": NOTICE_CORE,
        "steps_needed": 2,
        "multi_path_reason": (
            NOTICE_MULTI_PATH_REASON
        ),
    },
    {
        "id": "R02",
        "employee_id": "E-1001",
        "core": NOTICE_CORE,
        "optional": NOTICE_OPTIONAL,
        "dependency": NOTICE_CORE,
        "steps_needed": 2,
        "multi_path_reason": (
            NOTICE_MULTI_PATH_REASON
        ),
    },
    {
        "id": "R03",
        "employee_id": "E-1004",
        "core": NOTICE_CORE,
        "optional": NOTICE_OPTIONAL,
        "dependency": NOTICE_CORE,
        "steps_needed": 2,
        "multi_path_reason": (
            NOTICE_MULTI_PATH_REASON
        ),
    },
    {
        "id": "R04",
        "employee_id": "E-1005",
        "core": NOTICE_CORE,
        "optional": NOTICE_OPTIONAL,
        "dependency": NOTICE_CORE,
        "steps_needed": 2,
        "multi_path_reason": (
            NOTICE_MULTI_PATH_REASON
        ),
    },
    {
        "id": "R05",
        "employee_id": "E-1006",
        "core": NOTICE_CORE,
        "optional": NOTICE_OPTIONAL,
        "dependency": NOTICE_CORE,
        "steps_needed": 2,
        "multi_path_reason": (
            NOTICE_MULTI_PATH_REASON
        ),
    },
    {
        "id": "R06",
        "employee_id": "E-1003",
        "core": ("get_employee_record",),
        "optional": (),
        "dependency": None,
        "steps_needed": 1,
        "multi_path_reason": (
            "One fact, one source. The handbook does "
            "not know where anyone works and the "
            "statutory table does not know who "
            "anyone is, so there is no second "
            "defensible path and none is accepted."
        ),
    },
    {
        "id": "R07",
        "employee_id": "E-1002",
        "core": ("get_employee_record",),
        "optional": (),
        "dependency": None,
        "steps_needed": 1,
        "multi_path_reason": (
            "One fact, one source."
        ),
    },
    {
        "id": "R08",
        "employee_id": None,
        "core": ("get_jurisdiction_rules",),
        "optional": (),
        "dependency": None,
        "steps_needed": 1,
        "multi_path_reason": (
            "A statutory minimum is in the statutory "
            "table. The handbook tool's own "
            "description says it returns no "
            "statutory figures, so searching it here "
            "is not an alternate path, it is the "
            "wrong tool."
        ),
    },
    {
        "id": "R09",
        "employee_id": None,
        "core": ("search_handbook",),
        "optional": (),
        "dependency": None,
        "steps_needed": 1,
        "multi_path_reason": (
            "The company's own entitlement is only "
            "in the handbook. The statutory table "
            "holds a different number for the same "
            "words, which is the trap this case "
            "watches."
        ),
    },
    {
        "id": "R10",
        "employee_id": "E-1004",
        "core": ("get_employee_record",),
        "optional": (),
        "dependency": None,
        "steps_needed": 1,
        "multi_path_reason": (
            "One fact, one source."
        ),
    },
]


def accepted_paths(case: dict) -> set:
    """
    The set of tool sequences this case accepts.
    """

    return interleavings(
        case["core"],
        case["optional"],
    )


def allowed_tools(case: dict) -> set:
    """
    Every tool that appears in some accepted path.
    A call to anything else is a wrong-tool call.
    """

    return set(case["core"]) | set(
        case["optional"]
    )


def is_multi_path(case: dict) -> bool:

    return len(accepted_paths(case)) > 1


# ---------------------------------------------------
# 2. The replayed runs
#
# One plan per case. The comment on each says what
# the plan is modelling, because an authored failure
# with no stated mechanism is just a number someone
# wanted.
# ---------------------------------------------------


PLANS = {
    # Phrased as a question about the policy, with
    # the employee incidental, so the run answers it
    # from the policy side and never opens the
    # record. The jurisdiction is the one the
    # handbook reads as though it were written for.
    "R01": [
        (
            "tool",
            "search_handbook",
            {
                "query": (
                    "notice period on "
                    "resignation"
                )
            },
        ),
        (
            "tool",
            "get_jurisdiction_rules",
            {"jurisdiction": "UK"},
        ),
        ("answer_notice",),
    ],
    # The same question shape as R01 about an
    # employee with three years of service. Same
    # path, same guess - and this is the one where
    # the guess is wrong.
    "R02": [
        (
            "tool",
            "search_handbook",
            {
                "query": (
                    "notice period on "
                    "resignation"
                )
            },
        ),
        (
            "tool",
            "get_jurisdiction_rules",
            {"jurisdiction": "UK"},
        ),
        ("answer_notice",),
    ],
    # Phrased as a question about the person ("does
    # E-1004 need to give"), so the run opens the
    # record first. This is the healthy path.
    "R03": [
        (
            "tool",
            "get_employee_record",
            {"employee_id": "E-1004"},
        ),
        (
            "tool",
            "get_jurisdiction_rules",
            {"jurisdiction": "India"},
        ),
        ("answer_notice",),
    ],
    "R04": [
        (
            "tool",
            "get_employee_record",
            {"employee_id": "E-1005"},
        ),
        (
            "tool",
            "get_jurisdiction_rules",
            {"jurisdiction": "US"},
        ),
        ("answer_notice",),
    ],
    # The expensive one. No policy in this corpus
    # covers notice, so the handbook answers nothing
    # and the run re-asks it three times with
    # different wording before giving up on it and
    # guessing the jurisdiction. Same skip as R01,
    # plus the bill.
    "R05": [
        (
            "tool",
            "search_handbook",
            {"query": "notice period"},
        ),
        (
            "tool",
            "search_handbook",
            {
                "query": (
                    "resignation notice period "
                    "fixed term"
                )
            },
        ),
        (
            "tool",
            "search_handbook",
            {
                "query": (
                    "termination notice "
                    "requirement"
                )
            },
        ),
        (
            "tool",
            "get_jurisdiction_rules",
            {"jurisdiction": "UK"},
        ),
        ("answer_notice",),
    ],
    "R06": [
        (
            "tool",
            "get_employee_record",
            {"employee_id": "E-1003"},
        ),
        (
            "answer",
            {
                "answer": (
                    "E-1003 is employed in India."
                ),
                "value": "India",
                "sources": [],
            },
        ),
    ],
    "R07": [
        (
            "tool",
            "get_employee_record",
            {"employee_id": "E-1002"},
        ),
        (
            "answer",
            {
                "answer": (
                    "E-1002 has fourteen months "
                    "of service."
                ),
                "value": "14",
                "sources": [],
            },
        ),
    ],
    # Wrong tool. The question says "statutory", and
    # the run searches the handbook anyway and comes
    # back with the company's twenty-five days in
    # place of the statutory twenty-eight. Outcome
    # and trajectory both fail, which is what a
    # wrong-tool call usually looks like.
    "R08": [
        (
            "tool",
            "search_handbook",
            {
                "query": (
                    "statutory minimum annual "
                    "leave UK"
                )
            },
        ),
        (
            "answer",
            {
                "answer": (
                    "The minimum annual leave is "
                    "twenty-five days."
                ),
                "value": "25",
                "sources": [
                    {
                        "policy_id": "HR-202",
                        "section": "2.1",
                    }
                ],
            },
        ),
    ],
    "R09": [
        (
            "tool",
            "search_handbook",
            {
                "query": (
                    "annual leave entitlement "
                    "full-time employees"
                )
            },
        ),
        (
            "answer",
            {
                "answer": (
                    "Full-time employees receive "
                    "twenty-five days of paid "
                    "annual leave per leave year."
                ),
                "value": "25",
                "sources": [
                    {
                        "policy_id": "HR-202",
                        "section": "2.1",
                    }
                ],
            },
        ),
    ],
    # A made-up input: the id in the question is
    # E-1004 and the call goes out as E-1044. The
    # tool refuses it, so the damage is one wasted
    # step rather than a wrong answer - which is the
    # argument for tools that refuse.
    "R10": [
        (
            "tool",
            "get_employee_record",
            {"employee_id": "E-1044"},
        ),
        (
            "answer",
            {
                "answer": (
                    "E-1004 is a fixed-term "
                    "employee."
                ),
                "value": "fixed_term",
                "sources": [],
            },
        ),
    ],
}


# The policy the guessing runs cite for a notice
# figure. There is no HR-206 in this corpus - the
# citation is invented to dress up a guess, and the
# section check catches it.
INVENTED_CITATION = {
    "policy_id": "HR-206",
    "section": "4.2",
}


def estimate_tokens(text: str) -> int:

    return max(
        1,
        -(-len(text or "") // CHARS_PER_TOKEN),
    )


class ReplayModel:
    """
    A model that follows a written plan, and repairs
    itself when a tool refuses it.

    The repair rules are deliberately generic and the
    same on both arms: read the record a refusal asks
    for, then retry the refused call; re-read a record
    whose id the tool did not recognise, using the id
    in the question. Nothing in a plan knows which arm
    it is running under, so every difference between
    the two arms is something the tools did.
    """

    def __init__(
        self,
        case: dict,
        plan: list,
    ):

        self.case = case

        self.plan = list(plan)

        self.cursor = 0

        self.retry = None

        self.repairs = []

    # -- reading what has happened so far ----------

    @staticmethod
    def history(items: list) -> list:
        """
        The (name, arguments, result) of every tool
        call in the message list so far.
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

            elif (
                kind == "function_call_output"
            ):

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

    @staticmethod
    def last_good(
        history: list,
        name: str,
    ):

        for call in reversed(history):

            if call["name"] != name:
                continue

            if "error" in call["result"]:
                continue

            return call["result"]

        return None

    @staticmethod
    def required_arguments(
        tools: list,
        name: str,
    ) -> list:

        for schema in tools or []:

            if schema.get("name") == name:

                return schema.get(
                    "parameters",
                    {},
                ).get("required", [])

        return []

    # -- deciding the next move --------------------

    def fill(
        self,
        name: str,
        arguments: dict,
        tools: list,
        history: list,
    ) -> dict:
        """
        Fill a required argument from something the
        run has already read.

        A model fills a required field from what it
        has. If it has not read a record it has
        nothing to put there, and the call goes out
        short - which is exactly when the mitigated
        tool refuses it.
        """

        if name != "get_jurisdiction_rules":
            return arguments

        if (
            "tenure_months"
            not in self.required_arguments(
                tools,
                name,
            )
        ):
            return arguments

        record = self.last_good(
            history,
            "get_employee_record",
        )

        if record is None:
            return arguments

        return {
            **arguments,
            "tenure_months": record[
                "tenure_months"
            ],
        }

    def repair(
        self,
        last: dict,
        tools: list,
    ):

        error = str(last["result"]["error"])

        employee_id = self.case["employee_id"]

        if (
            "tenure_months is required" in error
            and employee_id
        ):

            self.retry = (
                last["name"],
                last["arguments"],
            )

            self.repairs.append(
                "read the record the refusal "
                "asked for"
            )

            return (
                "tool",
                "get_employee_record",
                {"employee_id": employee_id},
            )

        if (
            "No employee record for" in error
            and employee_id
        ):

            self.repairs.append(
                "re-read the record with the id "
                "from the question"
            )

            return (
                "tool",
                "get_employee_record",
                {"employee_id": employee_id},
            )

        return None

    def notice_answer(
        self,
        history: list,
    ) -> dict:
        """
        The answer to a notice question, derived from
        what this run actually read.

        Read the record and the branch is a fact.
        Skip it and the only thing left is a guess at
        the common case - a recent hire - and a
        citation invented to cover it, because no
        policy in this corpus states a notice period
        and an answer with no source looks unfinished.
        """

        rules = self.last_good(
            history,
            "get_jurisdiction_rules",
        )

        if rules is None:

            return {
                "answer": (
                    "I could not find the notice "
                    "period."
                ),
                "value": None,
                "sources": [],
            }

        record = self.last_good(
            history,
            "get_employee_record",
        )

        if record is not None:

            under = (
                record["tenure_months"]
                < TENURE_THRESHOLD_MONTHS
            )

            days = (
                rules[
                    "notice_days_under_2_years"
                ]
                if under
                else rules[
                    "notice_days_2_years_or_more"
                ]
            )

            return {
                "answer": (
                    f"{days} days, from the "
                    f"{rules['jurisdiction']} "
                    "statutory minimum for "
                    f"{record['tenure_months']} "
                    "months of service."
                ),
                "value": str(days),
                "sources": [],
            }

        days = rules["notice_days_under_2_years"]

        return {
            "answer": (
                f"The notice period is {days} "
                "days."
            ),
            "value": str(days),
            "sources": [dict(INVENTED_CITATION)],
        }

    def advance(
        self,
        history: list,
        tools: list,
    ):

        if self.cursor >= len(self.plan):

            return (
                "answer",
                {
                    "answer": (
                        "Stopped without an "
                        "answer."
                    ),
                    "value": None,
                    "sources": [],
                },
            )

        step = self.plan[self.cursor]

        self.cursor += 1

        if step[0] == "answer_notice":

            return (
                "answer",
                self.notice_answer(history),
            )

        if step[0] == "answer":
            return step

        return (
            "tool",
            step[1],
            self.fill(
                step[1],
                step[2],
                tools,
                history,
            ),
        )

    def choose(
        self,
        items: list,
        tools: list,
    ):

        history = self.history(items)

        last = history[-1] if history else None

        if (
            last
            and isinstance(
                last["result"],
                dict,
            )
            and "error" in last["result"]
        ):

            repaired = self.repair(last, tools)

            if repaired is not None:
                return repaired

        if self.retry is not None:

            name, arguments = self.retry

            self.retry = None

            return (
                "tool",
                name,
                self.fill(
                    name,
                    arguments,
                    tools,
                    history,
                ),
            )

        return self.advance(history, tools)

    # -- the model interface -----------------------

    def __call__(
        self,
        instructions: str,
        items: list,
        tools: list = None,
    ) -> dict:

        # Counted off the payload the loop is really
        # sending, including the tool schemas, so a
        # bigger schema and an extra lap both show up
        # on the bill.
        input_tokens = (
            estimate_tokens(instructions)
            + estimate_tokens(
                json.dumps(items)
            )
            + estimate_tokens(
                json.dumps(tools or [])
            )
        )

        step = self.choose(items, tools)

        if step[0] == "answer":

            text = json.dumps(step[1])

            return {
                "tool_calls": [],
                "text": text,
                "input_tokens": input_tokens,
                "output_tokens": (
                    estimate_tokens(text)
                ),
            }

        name, arguments = step[1], step[2]

        emitted = json.dumps(
            {
                "name": name,
                "arguments": arguments,
            }
        )

        return {
            "tool_calls": [
                {
                    "call_id": (
                        f"call_{len(items)}"
                    ),
                    "name": name,
                    "arguments": arguments,
                }
            ],
            "text": None,
            "input_tokens": input_tokens,
            "output_tokens": estimate_tokens(
                emitted
            ),
        }


# ---------------------------------------------------
# 3. Scoring one run
# ---------------------------------------------------


def observed_path(record: list) -> tuple:
    """
    The tools that actually carried information.

    A refused call hands the model nothing, so it
    does not enter the path - but it is still counted
    as a step and still counted as a refusal, so it
    is never free.
    """

    return tuple(
        call["name"]
        for call in record
        if "error" not in call["result"]
    )


def check_arguments(
    case: dict,
    record: list,
    final: dict,
    sections: set,
    schemas: list,
) -> list:
    """
    Every argument value the run produced, and every
    section it cited, checked against something real.

    Four kinds of failure, kept apart because they
    mean different things:

      nonexistent   the value is not in the fixture
                    or not in the index - fluent
                    fiction
      unestablished the value exists, but this run
                    never read it; it was supplied
                    from nowhere
      missing       a required argument was left out
      empty         a free-text argument was blank
    """

    employees = load_fixture()["employees"]

    required = {
        schema["name"]: schema.get(
            "parameters",
            {},
        ).get("required", [])
        for schema in schemas
    }

    checks = []

    for index, call in enumerate(record):

        name = call["name"]

        arguments = call["arguments"]

        refused = "error" in call["result"]

        for argument in required.get(
            name,
            [],
        ):

            if argument not in arguments:

                checks.append(
                    {
                        "target": (
                            f"{name}.{argument}"
                        ),
                        "value": None,
                        "ok": False,
                        "kind": "missing",
                        "detail": (
                            "required argument "
                            "not supplied"
                        ),
                        "refused": refused,
                    }
                )

        if name == "get_employee_record":

            value = arguments.get(
                "employee_id"
            )

            checks.append(
                {
                    "target": (
                        "get_employee_record."
                        "employee_id"
                    ),
                    "value": value,
                    "ok": value in employees,
                    "kind": (
                        "ok"
                        if value in employees
                        else "nonexistent"
                    ),
                    "detail": (
                        "in the fixture"
                        if value in employees
                        else (
                            "no such employee "
                            "id"
                        )
                    ),
                    "refused": refused,
                }
            )

        if name == "get_jurisdiction_rules":

            value = arguments.get(
                "jurisdiction"
            )

            real = value in JURISDICTIONS

            # A jurisdiction is only a fact about
            # this employee if this run read it off
            # their record. Supplied any other way it
            # is a guess wearing a valid enum value.
            read_before = any(
                earlier["name"]
                == "get_employee_record"
                and "error"
                not in earlier["result"]
                for earlier in record[:index]
            )

            established = (
                read_before
                or case["employee_id"] is None
            )

            checks.append(
                {
                    "target": (
                        "get_jurisdiction_rules."
                        "jurisdiction"
                    ),
                    "value": value,
                    "ok": real and established,
                    "kind": (
                        "ok"
                        if real and established
                        else (
                            "nonexistent"
                            if not real
                            else "unestablished"
                        )
                    ),
                    "detail": (
                        "read from the record"
                        if real and established
                        else (
                            "not a known "
                            "jurisdiction"
                            if not real
                            else (
                                "never read "
                                "from any "
                                "record in "
                                "this run"
                            )
                        )
                    ),
                    "refused": refused,
                }
            )

            if "tenure_months" in arguments:

                claimed = arguments[
                    "tenure_months"
                ]

                stored = (
                    employees.get(
                        case["employee_id"],
                        {},
                    ).get("tenure_months")
                )

                matches = claimed == stored

                checks.append(
                    {
                        "target": (
                            "get_jurisdiction_"
                            "rules.tenure_months"
                        ),
                        "value": claimed,
                        "ok": matches,
                        "kind": (
                            "ok"
                            if matches
                            else "nonexistent"
                        ),
                        "detail": (
                            "matches the record"
                            if matches
                            else (
                                "does not match "
                                f"the record "
                                f"({stored})"
                            )
                        ),
                        "refused": refused,
                    }
                )

        if name == "search_handbook":

            value = arguments.get("query")

            filled = bool(
                isinstance(value, str)
                and value.strip()
            )

            checks.append(
                {
                    "target": (
                        "search_handbook.query"
                    ),
                    "value": value,
                    "ok": filled,
                    "kind": (
                        "ok" if filled else "empty"
                    ),
                    "detail": (
                        "non-empty"
                        if filled
                        else "blank query"
                    ),
                    "refused": refused,
                }
            )

    for source in final.get("sources") or []:

        key = (
            source.get("policy_id", ""),
            source.get("section", ""),
        )

        real = key in sections

        checks.append(
            {
                "target": "citation",
                "value": f"{key[0]}/{key[1]}",
                "ok": real,
                "kind": (
                    "ok"
                    if real
                    else "nonexistent_section"
                ),
                "detail": (
                    "section is in the index"
                    if real
                    else (
                        "no such section in the "
                        "index"
                    )
                ),
                "refused": False,
            }
        )

    return checks


# The zoo. Every mode this eval can see, defined
# where it is counted rather than in prose somewhere
# else.
MODES = [
    # Produced a figure that depends on a fact it
    # never read. The right-answer-wrong-path mode,
    # and the one this week is hunting.
    "skipped_dependency",
    # Called a tool that cannot answer this question.
    "wrong_tool",
    # Asked a source it had already read.
    "loop",
    # Passed an argument value that does not exist.
    "hallucinated_argument",
    # Cited a policy section that is not in the index.
    "fabricated_citation",
    # Spent a step being refused by a tool.
    "rejected_call_retry",
    # Stopped without an answer and without saying so.
    "quiet_giveup",
]

# The split that decides what fails a trajectory.
# A correctness mode means the reasoning was wrong. A
# cost mode means the run reached its conclusion by a
# wasteful route: real, reported and priced, but not a
# reason to call the path wrong.
CORRECTNESS_MODES = [
    "skipped_dependency",
    "wrong_tool",
    "hallucinated_argument",
    "fabricated_citation",
    "quiet_giveup",
]

COST_MODES = [
    "loop",
    "rejected_call_retry",
]


GAVE_UP_PHRASES = [
    "could not",
    "couldn't",
    "not able",
    "no information",
    "unable",
]


def detect_modes(
    case: dict,
    record: list,
    result: dict,
    checks: list,
) -> list:

    modes = []

    successful = [
        call
        for call in record
        if "error" not in call["result"]
    ]

    dependency = case["dependency"]

    if dependency:

        first, then = dependency

        read_first = False

        for call in successful:

            if call["name"] == first:
                read_first = True

            if (
                call["name"] == then
                and not read_first
            ):

                modes.append(
                    "skipped_dependency"
                )

                break

    permitted = allowed_tools(case)

    if any(
        call["name"] not in permitted
        for call in successful
    ):
        modes.append("wrong_tool")

    counts = {}

    for call in successful:

        counts[call["name"]] = (
            counts.get(call["name"], 0) + 1
        )

    if any(
        count > 1 for count in counts.values()
    ):
        modes.append("loop")

    kinds = {check["kind"] for check in checks}

    if "nonexistent" in kinds:
        modes.append("hallucinated_argument")

    if "nonexistent_section" in kinds:
        modes.append("fabricated_citation")

    if any(
        "error" in call["result"]
        for call in record
    ):
        modes.append("rejected_call_retry")

    said_so = any(
        phrase
        in (result.get("answer") or "").lower()
        for phrase in GAVE_UP_PHRASES
    )

    if result.get("terminated_by") or (
        result.get("value") is None
        and not said_so
    ):
        modes.append("quiet_giveup")

    return modes


def run_case(
    case: dict,
    question: dict,
    model_call,
    toolset,
    sections: set,
) -> dict:
    """
    One question, one arm, fully scored.
    """

    record = []

    def dispatch(
        name: str,
        arguments: dict,
    ) -> dict:
        """
        The real toolset, with a tap on it. The
        loop's own trace truncates results at 200
        characters, which is fine for reading and
        useless for scoring.
        """

        outcome = toolset.call(name, arguments)

        record.append(
            {
                "name": name,
                "arguments": arguments,
                "result": outcome,
            }
        )

        return outcome

    result = run_agent(
        question["question"],
        model_call,
        Budgets(),
        tool_schemas=toolset.schemas,
        tool_call=dispatch,
    )

    final = {
        "answer": result["answer"],
        "value": result["value"],
        "sources": result["sources"],
    }

    path = observed_path(record)

    accepted = accepted_paths(case)

    checks = check_arguments(
        case,
        record,
        final,
        sections,
        toolset.schemas,
    )

    modes = detect_modes(
        case,
        record,
        result,
        checks,
    )

    outcome_passed = value_matches(
        result["value"],
        question["expected_value"],
    )

    path_ok = path in accepted

    # A refused call told the model nothing and
    # changed no answer. What it claimed is still
    # recorded in the validity rate, because it says
    # something about the model - but it cannot fail a
    # run that then went and read the fact. The step
    # it cost is counted as a step and as a refusal.
    invented = [
        check
        for check in checks
        if not check["ok"]
        and not check["refused"]
        and check["kind"] != "missing"
    ]

    correctness = [
        mode
        for mode in modes
        if mode in CORRECTNESS_MODES
    ]

    # A trajectory passes when the run took an
    # accepted path, supplied nothing it had not read,
    # and tripped no correctness mode. All three,
    # because any one of them on its own can be true
    # of a bad run.
    trajectory_passed = (
        path_ok
        and not invented
        and not correctness
    )

    arguments_ok = not invented

    steps_taken = len(record)

    return {
        "id": case["id"],
        "question": question["question"],
        "expected": question["expected_value"],
        "value": result["value"],
        "outcome_passed": outcome_passed,
        "trajectory_passed": trajectory_passed,
        "path": list(path),
        "path_accepted": path_ok,
        "accepted_paths": sorted(
            list(item) for item in accepted
        ),
        "multi_path": is_multi_path(case),
        "arguments_ok": arguments_ok,
        "invented_values": [
            {
                "target": check["target"],
                "value": check["value"],
                "kind": check["kind"],
            }
            for check in invented
        ],
        "checks": checks,
        "modes": modes,
        "correctness_modes": correctness,
        "steps_taken": steps_taken,
        "steps_needed": case["steps_needed"],
        "step_efficiency": round(
            steps_taken / case["steps_needed"],
            3,
        ),
        "model_calls": result["usage"]["calls"],
        "total_tokens": result["usage"][
            "total_tokens"
        ],
        "cost_usd": result["usage"]["cost_usd"],
        # Every figure this run actually read from a
        # tool. The output guardrail in
        # injection_probe.py checks a numeric answer
        # against this set, so it has to be recorded
        # while the results are still in hand.
        "figures_seen": sorted(
            {
                digits
                for call in record
                for digits in re.findall(
                    r"\d+",
                    json.dumps(call["result"]),
                )
            }
        ),
        "terminated_by": result[
            "terminated_by"
        ],
        "answer": result["answer"],
        "sources": result["sources"],
        "calls": [
            {
                "name": call["name"],
                "arguments": call["arguments"],
                "refused": (
                    "error" in call["result"]
                ),
            }
            for call in record
        ],
        "log": result["log"],
    }


# ---------------------------------------------------
# 4. One arm, and the four numbers
# ---------------------------------------------------


def load_questions() -> dict:

    with open(
        QUESTIONS_PATH,
        "r",
        encoding="utf-8",
    ) as file:

        return {
            question["id"]: question
            for question in json.load(file)
        }


def run_arm(
    name: str,
    questions: dict,
    sections: set,
    retriever=None,
    validate_tenure: bool = False,
    sanitise: bool = False,
    live_model=None,
) -> list:

    toolset = build_toolset(
        validate_tenure=validate_tenure,
        sanitise=sanitise,
        retriever=retriever,
    )

    rows = []

    for case in CASES:

        model_call = (
            live_model
            if live_model is not None
            else ReplayModel(
                case,
                PLANS[case["id"]],
            )
        )

        rows.append(
            run_case(
                case,
                questions[case["id"]],
                model_call,
                toolset,
                sections,
            )
        )

    return rows


def summarise(rows: list) -> dict:
    """
    The four trajectory numbers, plus the gap.

    Cost is reported at p50 and max. The mean is the
    one number that hides the run that looped, and
    the run that looped is the one on the bill.
    """

    total_calls = sum(
        len(row["calls"]) for row in rows
    )

    wrong_tool_calls = sum(
        1
        for row in rows
        for call in row["calls"]
        if call["name"]
        not in allowed_tools(
            next(
                case
                for case in CASES
                if case["id"] == row["id"]
            )
        )
    )

    checks = [
        check
        for row in rows
        for check in row["checks"]
    ]

    costs = [row["cost_usd"] for row in rows]

    outcome_rate = sum(
        1
        for row in rows
        if row["outcome_passed"]
    ) / len(rows)

    trajectory_rate = sum(
        1
        for row in rows
        if row["trajectory_passed"]
    ) / len(rows)

    mode_counts = {
        mode: sum(
            1
            for row in rows
            if mode in row["modes"]
        )
        for mode in MODES
    }

    return {
        "cases": len(rows),
        "tool_calls": total_calls,
        "tool_choice_accuracy": round(
            (total_calls - wrong_tool_calls)
            / total_calls,
            3,
        ),
        "wrong_tool_calls": wrong_tool_calls,
        "argument_checks": len(checks),
        "argument_validity_rate": round(
            sum(
                1
                for check in checks
                if check["ok"]
            )
            / len(checks),
            3,
        ),
        "invalid_arguments": [
            {
                "target": check["target"],
                "value": check["value"],
                "kind": check["kind"],
            }
            for check in checks
            if not check["ok"]
        ],
        "step_efficiency_mean": round(
            statistics.mean(
                row["step_efficiency"]
                for row in rows
            ),
            3,
        ),
        "step_efficiency_max": round(
            max(
                row["step_efficiency"]
                for row in rows
            ),
            3,
        ),
        "steps_taken": sum(
            row["steps_taken"] for row in rows
        ),
        "steps_needed": sum(
            row["steps_needed"] for row in rows
        ),
        "cost_per_question_p50": round(
            statistics.median(costs),
            6,
        ),
        "cost_per_question_max": round(
            max(costs),
            6,
        ),
        "cost_per_question_mean": round(
            statistics.mean(costs),
            6,
        ),
        "tokens_per_question_p50": int(
            statistics.median(
                row["total_tokens"]
                for row in rows
            )
        ),
        "tokens_per_question_max": max(
            row["total_tokens"] for row in rows
        ),
        "model_calls_total": sum(
            row["model_calls"] for row in rows
        ),
        "outcome_pass_rate": round(
            outcome_rate,
            3,
        ),
        "trajectory_pass_rate": round(
            trajectory_rate,
            3,
        ),
        "gap": round(
            outcome_rate - trajectory_rate,
            3,
        ),
        "mode_counts": mode_counts,
    }


# ---------------------------------------------------
# 5. Printing
# ---------------------------------------------------


def print_cases(
    name: str,
    rows: list,
):

    print(f"\n{name} - per case")

    print(
        f"{'id':<5}{'out':<6}{'traj':<6}"
        f"{'steps':<7}{'eff':<6}{'$/q':<11}"
        f"modes"
    )

    print("-" * 78)

    for row in rows:

        print(
            f"{row['id']:<5}"
            f"{('PASS' if row['outcome_passed'] else 'FAIL'):<6}"
            f"{('PASS' if row['trajectory_passed'] else 'FAIL'):<6}"
            f"{str(row['steps_taken']) + '/' + str(row['steps_needed']):<7}"
            f"{row['step_efficiency']:<6}"
            f"{row['cost_usd']:<11}"
            f"{', '.join(row['modes']) or '-'}"
        )


def print_summary(summaries: dict):

    rows = [
        (
            "tool-choice accuracy",
            "tool_choice_accuracy",
        ),
        (
            "  wrong-tool calls",
            "wrong_tool_calls",
        ),
        (
            "  tool calls total",
            "tool_calls",
        ),
        (
            "argument validity rate",
            "argument_validity_rate",
        ),
        (
            "  argument checks",
            "argument_checks",
        ),
        (
            "step efficiency (mean)",
            "step_efficiency_mean",
        ),
        (
            "step efficiency (max)",
            "step_efficiency_max",
        ),
        (
            "cost per question p50",
            "cost_per_question_p50",
        ),
        (
            "cost per question max",
            "cost_per_question_max",
        ),
        (
            "tokens per question p50",
            "tokens_per_question_p50",
        ),
        (
            "tokens per question max",
            "tokens_per_question_max",
        ),
        (
            "model calls (10 questions)",
            "model_calls_total",
        ),
        (
            "outcome pass rate",
            "outcome_pass_rate",
        ),
        (
            "trajectory pass rate",
            "trajectory_pass_rate",
        ),
        (
            "outcome-vs-trajectory gap",
            "gap",
        ),
    ]

    names = list(summaries)

    print("\nthe numbers")

    header = f"{'metric':<28}"

    for name in names:
        header += f"{name:>14}"

    print(header)

    print("-" * (28 + 14 * len(names)))

    for label, key in rows:

        line = f"{label:<28}"

        for name in names:
            line += f"{summaries[name][key]:>14}"

        print(line)


def print_modes(summaries: dict):

    names = list(summaries)

    print("\nper-mode counts (out of 10 cases)")

    header = f"{'mode':<24}"

    for name in names:
        header += f"{name:>12}"

    header += f"{'change':>9}"

    print(header)

    print("-" * (33 + 12 * len(names)))

    for mode in MODES:

        counts = [
            summaries[name]["mode_counts"][
                mode
            ]
            for name in names
        ]

        label = (
            f"{mode} (cost)"
            if mode in COST_MODES
            else mode
        )

        line = f"{label:<24}"

        for count in counts:
            line += f"{count:>12}"

        change = counts[-1] - counts[0]

        line += (
            f"{('same' if change == 0 else f'{change:+d}'):>9}"
        )

        if change > 0:
            line += "  <- worse"

        print(line)


def right_answer_wrong_path(
    rows: list,
) -> list:

    return [
        row
        for row in rows
        if row["outcome_passed"]
        and not row["trajectory_passed"]
    ]


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "drive the loop with the real model "
            "instead of the replayed plans"
        ),
    )

    arguments = parser.parse_args()

    if (
        INPUT_COST_PER_1M == 0
        and OUTPUT_COST_PER_1M == 0
    ):
        print(
            "Token prices are unset, so every "
            "cost below will be 0.00. Set "
            "INPUT_COST_PER_1M and "
            "OUTPUT_COST_PER_1M in .env from the "
            "provider's pricing page."
        )

    questions = load_questions()

    missing = [
        case["id"]
        for case in CASES
        if case["id"] not in questions
    ]

    if missing:
        raise SystemExit(
            f"Missing questions: {missing}"
        )

    retriever, handbook_source = (
        build_handbook()
    )

    sections = valid_sections()

    live_model = None

    if arguments.live:

        from evaluation.race import (
            build_model_call,
        )

        live_model, error = build_model_call()

        if error:
            raise SystemExit(
                f"Model unavailable: {error}"
            )

    print(
        f"\nmodel      : "
        f"{OPENAI_MODEL if arguments.live else 'replayed plans (no API)'}"
    )

    print(
        f"handbook   : {handbook_source}"
    )

    print(
        f"sections   : {len(sections)} "
        "(policy_id, section) pairs in the index"
    )

    print(
        f"prices     : in "
        f"${INPUT_COST_PER_1M}/1M  out "
        f"${OUTPUT_COST_PER_1M}/1M"
    )

    arms = {
        "baseline": {
            "validate_tenure": False
        },
        "validated": {
            "validate_tenure": True
        },
    }

    results = {}

    for name, options in arms.items():

        results[name] = run_arm(
            name,
            questions,
            sections,
            retriever=retriever,
            live_model=live_model,
            **options,
        )

        print_cases(name, results[name])

    summaries = {
        name: summarise(rows)
        for name, rows in results.items()
    }

    print_summary(summaries)

    print_modes(summaries)

    lucky = right_answer_wrong_path(
        results["baseline"]
    )

    print(
        "\nright answer, wrong path "
        f"({len(lucky)} of 10 in baseline)"
    )

    for row in lucky:

        print(
            f"  {row['id']} value={row['value']} "
            f"expected={row['expected']} "
            f"path={' > '.join(row['path'])} "
            f"modes={', '.join(row['modes'])}"
        )

    with open(
        RESULTS_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            {
                "config": {
                    "model": (
                        OPENAI_MODEL
                        if arguments.live
                        else "replayed_plans"
                    ),
                    "handbook_source": (
                        handbook_source
                    ),
                    "input_cost_per_1m": (
                        INPUT_COST_PER_1M
                    ),
                    "output_cost_per_1m": (
                        OUTPUT_COST_PER_1M
                    ),
                    "chars_per_token": (
                        CHARS_PER_TOKEN
                    ),
                    "budgets": {
                        "max_iterations": (
                            Budgets().max_iterations
                        ),
                        "max_tokens": (
                            Budgets().max_tokens
                        ),
                        "max_cost_usd": (
                            Budgets().max_cost_usd
                        ),
                        "max_seconds": (
                            Budgets().max_seconds
                        ),
                    },
                },
                "expected_sequences": [
                    {
                        "id": case["id"],
                        "steps_needed": case[
                            "steps_needed"
                        ],
                        "multi_path": (
                            is_multi_path(case)
                        ),
                        "accepted_paths": sorted(
                            list(path)
                            for path in (
                                accepted_paths(
                                    case
                                )
                            )
                        ),
                        "why": case[
                            "multi_path_reason"
                        ],
                    }
                    for case in CASES
                ],
                "summary": summaries,
                "arms": results,
            },
            file,
            indent=2,
        )

    print(f"\nWrote {RESULTS_PATH}.")


if __name__ == "__main__":
    main()
