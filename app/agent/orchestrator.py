"""
The policy squad: one manager, two specialists.

    manager        decomposes the question, decides
                   who to call, synthesises the answer
    policy worker  reads the handbook, nothing else
    eligibility    reads the employee record and the
      worker       statutory table, nothing else

Each worker gets a narrow prompt and a subset of the
tools - which is the only plausible source of a win
over the single agent, so handing either one the full
toolset would delete the thing being tested.

WHAT THIS FILE MEASURES
-----------------------
Every hand-off is recorded with its own token count,
split into the part that is new for this hand-off and
the part that is context sent again. A team's bill is
mostly the second number, and you cannot argue about
re-send cost without showing it per hand-off.

A hand-off here is one call to a worker. The worker
runs the ordinary Week-7 `run_agent` loop, so a
worker that loops pays for looping exactly as the
single agent does, and the two arms are counted by
the same ruler.
"""

import json
import time
from dataclasses import dataclass, field

from app.agent.loop import (
    Budgets,
    Usage,
    parse_final,
    run_agent,
)
from app.agent.tools import build_toolset


# ---------------------------------------------------
# Worker definitions
#
# Narrow prompt, narrow toolset. The manager is the
# only component that sees the whole question.
# ---------------------------------------------------


POLICY_WORKER_PROMPT = """
You are the policy retrieval specialist.

Your only job is to find the handbook passages that
answer the question and report them. You have one
tool and it reads the policy documents.

Do not calculate entitlements, do not reason about
any individual employee, and do not answer from
memory. If the handbook does not cover the question,
say so plainly.

Reply with JSON only:

{
  "answer": "what the policy says, one or two sentences",
  "value": "the single key figure if there is one, else null",
  "sources": [{"policy_id": "HR-202", "section": "2.1"}]
}

Cite only sections you actually read from the tool.
"""


ELIGIBILITY_WORKER_PROMPT = """
You are the eligibility calculation specialist.

Your only job is to read an employee's record and the
statutory table for their jurisdiction, and state
which figure applies to them.

You cannot see the handbook. Do not quote policy
prose and do not invent a policy citation.

Notice depends on length of service, so read the
record before the statutory table.

Reply with JSON only:

{
  "answer": "which figure applies and why, one or two sentences",
  "value": "the single key figure, digits only where it is a number of days",
  "sources": []
}

Use "value": null if the question needs no figure
from your two sources.
"""


MANAGER_PROMPT = """
You are the manager of a two-specialist HR team.

You decide which specialists to consult, then write
the final answer from what they return. You have no
tools of your own and no knowledge of your own.

Your specialists:

  policy       reads the handbook. Use it for what
               the company's written policy says.
  eligibility  reads one employee's record and the
               statutory table. Use it only when the
               question is about a named employee's
               own entitlement.

Do not state a figure no specialist returned. If a
specialist fails, say what you could not establish
rather than filling the gap yourself.

Reply with JSON only:

{
  "answer": "one or two sentences",
  "value": "the single key figure, else null",
  "sources": [{"policy_id": "HR-202", "section": "2.1"}]
}

Cite only sections a specialist reported.
"""


POLICY_TOOLS = ("search_handbook",)

ELIGIBILITY_TOOLS = (
    "get_employee_record",
    "get_jurisdiction_rules",
)


class WorkerFailure(Exception):
    """
    A worker that returned an error status rather
    than a result. Carries the code so the manager's
    handling can be told apart from a crash.
    """

    def __init__(
        self,
        worker: str,
        status: int,
        detail: str = "",
    ):

        self.worker = worker

        self.status = status

        self.detail = detail

        super().__init__(
            f"{worker} returned {status}. {detail}".strip()
        )


# ---------------------------------------------------
# Hand-off accounting
# ---------------------------------------------------


@dataclass
class Handoff:
    """
    One call from the manager to a worker, and what
    it cost.

    `resent_tokens` is the part of the input that the
    orchestrator had already paid to send at least
    once - the question and any prior worker output
    forwarded into this worker's brief. `new_tokens`
    is what is genuinely new to this hand-off: the
    worker's own system prompt and tool schemas.
    """

    index: int

    sender: str

    receiver: str

    brief: str

    input_tokens: int = 0

    output_tokens: int = 0

    resent_tokens: int = 0

    seconds: float = 0.0

    status: str = "ok"

    detail: str = ""

    # How many model round trips this hand-off cost.
    # A worker that loops makes more than one.
    model_calls: int = 1

    @property
    def total_tokens(self) -> int:

        return (
            self.input_tokens
            + self.output_tokens
        )

    @property
    def new_tokens(self) -> int:

        return max(
            0,
            self.total_tokens
            - self.resent_tokens,
        )

    def as_dict(self) -> dict:

        return {
            "index": self.index,
            "sender": self.sender,
            "receiver": self.receiver,
            "brief": self.brief,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "resent_tokens": self.resent_tokens,
            "new_tokens": self.new_tokens,
            "model_calls": self.model_calls,
            "seconds": round(self.seconds, 3),
            "status": self.status,
            "detail": self.detail,
        }

    def line(self) -> str:
        """
        One log line. Fixed width so the log can be
        read as a table.
        """

        return (
            f"[{self.index:>2}] "
            f"{self.sender:<12} -> "
            f"{self.receiver:<12} "
            f"in={self.input_tokens:>6} "
            f"out={self.output_tokens:>5} "
            f"total={self.total_tokens:>6} "
            f"resent={self.resent_tokens:>6} "
            f"new={self.new_tokens:>5} "
            f"{self.seconds:>6.3f}s "
            f"{self.status:<9} "
            f"{self.brief}"
        )


@dataclass
class HandoffLog:

    case_id: str = ""

    entries: list = field(
        default_factory=list
    )

    def add(
        self,
        handoff: Handoff,
    ):

        self.entries.append(handoff)

    def next_index(self) -> int:

        return len(self.entries) + 1

    @property
    def total_tokens(self) -> int:

        return sum(
            entry.total_tokens
            for entry in self.entries
        )

    @property
    def resent_tokens(self) -> int:

        return sum(
            entry.resent_tokens
            for entry in self.entries
        )

    def largest(self):
        """
        The single hand-off with the biggest token
        share, which is the one worth naming when
        attributing the bill.
        """

        if not self.entries:
            return None

        return max(
            self.entries,
            key=lambda entry: entry.total_tokens,
        )

    def lines(self) -> list[str]:

        return [
            entry.line()
            for entry in self.entries
        ]

    def as_dicts(self) -> list[dict]:

        return [
            entry.as_dict()
            for entry in self.entries
        ]


# ---------------------------------------------------
# The workers
# ---------------------------------------------------


def subset_toolset(
    names: tuple,
    retriever=None,
):
    """
    The full toolset narrowed to `names`.

    Built from `build_toolset` so a worker runs the
    real tools over the real fixture and the real
    index, not a stub.
    """

    full = build_toolset(retriever=retriever)

    schemas = [
        schema
        for schema in full.schemas
        if schema["name"] in names
    ]

    functions = {
        name: function
        for name, function in (
            full.functions.items()
        )
        if name in names
    }

    full.schemas = schemas

    full.functions = functions

    full.name = "+".join(names)

    return full


def run_worker(
    worker: str,
    brief: str,
    model_call,
    toolset,
    budgets: Budgets,
) -> dict:
    """
    One specialist, running the ordinary agent loop.

    The loop is `app.agent.loop.run_agent` unchanged,
    so a worker is measured exactly the way the
    single agent is.
    """

    prompt = (
        POLICY_WORKER_PROMPT
        if worker == "policy"
        else ELIGIBILITY_WORKER_PROMPT
    )

    def worker_model_call(
        instructions,
        items,
        tools,
    ):
        # The loop passes its own system prompt. The
        # worker's narrow prompt replaces it, which
        # is what makes this a specialist.
        return model_call(
            prompt,
            items,
            tools,
            worker=worker,
        )

    return run_agent(
        brief,
        worker_model_call,
        budgets,
        tool_schemas=toolset.schemas,
        tool_call=toolset.call,
    )


# ---------------------------------------------------
# The manager
# ---------------------------------------------------


def needs_eligibility(
    question: str,
    plan: dict | None,
) -> bool:
    """
    Whether the eligibility specialist is consulted.

    The manager's decision is the model's to make;
    this is only the fallback used when a plan does
    not state one, so the control flow is defined
    with no model present.
    """

    if plan is not None:
        return bool(
            plan.get("use_eligibility", False)
        )

    lowered = question.lower()

    return "e-" in lowered


def summarise_for_manager(
    worker: str,
    result: dict,
) -> dict:
    """
    What the manager is told about a worker's run.

    Only the answer, the figure and the citations
    travel. The worker's own tool transcript does
    not, because forwarding a full transcript into
    the manager's context is the re-send cost this
    week is about and it is not necessary here.
    """

    return {
        "worker": worker,
        "answer": result.get("answer", ""),
        "value": result.get("value"),
        "sources": result.get("sources", []),
    }


def run_orchestrator(
    question: str,
    model_call,
    budgets: Budgets | None = None,
    retriever=None,
    plan: dict | None = None,
    fail_policy_worker: bool = False,
    case_id: str = "",
) -> dict:
    """
    Manager plus two specialists on one question.

    `fail_policy_worker` injects the Week-10 failure:
    the policy retrieval worker returns a 500 instead
    of a result. What the manager does about it is
    not scripted here - it is whatever the manager
    does, which is the point of injecting it.

    `model_call(instructions, items, tools, worker=)`
    is the same callable the single agent uses, with
    one extra keyword naming which component is
    speaking.
    """

    budgets = budgets or Budgets()

    usage = Usage()

    log = HandoffLog(case_id=case_id)

    started = time.monotonic()

    worker_reports = []

    failures = []

    def record(
        sender: str,
        receiver: str,
        brief: str,
        result: dict,
        resent: int,
        status: str = "ok",
        detail: str = "",
    ):
        """
        `resent` is the brief's own token count: the
        context the sender was already holding and
        paid to send again.

        It is multiplied by the number of model calls
        the receiver made, because the loop re-sends
        its whole message list on every lap. A worker
        that takes three laps has been handed the
        same forwarded brief three times, and a
        hand-off cost that counted it once would
        understate the bill in exactly the direction
        that flatters the pattern.
        """

        worker_usage = result.get(
            "usage",
            {},
        )

        laps = max(
            1,
            worker_usage.get("calls", 1),
        )

        handoff = Handoff(
            index=log.next_index(),
            sender=sender,
            receiver=receiver,
            brief=brief,
            input_tokens=worker_usage.get(
                "input_tokens",
                0,
            ),
            output_tokens=worker_usage.get(
                "output_tokens",
                0,
            ),
            resent_tokens=(
                resent * laps
                if status == "ok"
                else resent
            ),
            seconds=result.get("seconds", 0.0),
            status=status,
            detail=detail,
        )

        log.add(handoff)

        usage.add(
            handoff.input_tokens,
            handoff.output_tokens,
        )

        # `Usage.add` counts one call per invocation,
        # but a worker that took three laps made
        # three round trips. Correct the count up so
        # the squad is charged for every sequential
        # call it really makes, which is the number
        # its latency will be made of once the model
        # is live.
        usage.calls += laps - 1

        handoff.model_calls = laps

        return handoff

    # ---- hand-off 1: manager -> policy worker ----
    #
    # The question is forwarded verbatim. Those are
    # tokens the orchestrator pays for a second time:
    # the manager was already holding them.
    policy_report = None

    policy_brief = question

    policy_toolset = subset_toolset(
        POLICY_TOOLS,
        retriever=retriever,
    )

    if fail_policy_worker:

        failure = WorkerFailure(
            "policy",
            500,
            "retrieval backend unavailable",
        )

        failures.append(
            {
                "worker": "policy",
                "status": 500,
                "detail": str(failure),
            }
        )

        record(
            "manager",
            "policy",
            policy_brief,
            {
                "usage": {},
                "seconds": 0.0,
            },
            resent=estimate_tokens(
                policy_brief
            ),
            status="FAILED",
            detail="HTTP 500 retrieval backend unavailable",
        )

    else:

        policy_result = run_worker(
            "policy",
            policy_brief,
            model_call,
            policy_toolset,
            budgets,
        )

        record(
            "manager",
            "policy",
            policy_brief,
            policy_result,
            resent=estimate_tokens(
                policy_brief
            ),
        )

        policy_report = summarise_for_manager(
            "policy",
            policy_result,
        )

        worker_reports.append(policy_report)

    # ---- hand-off 2: manager -> eligibility ------
    #
    # Sequential on purpose. The eligibility figure
    # depends on what the policy worker found, so
    # these two cannot be run in parallel and the
    # latency is not a defect of the pattern.
    if needs_eligibility(question, plan):

        eligibility_brief = (
            f"{question}\n\n"
            "What the policy specialist reported:\n"
            f"{json.dumps(policy_report, indent=2)}"
            if policy_report is not None
            else question
        )

        eligibility_toolset = subset_toolset(
            ELIGIBILITY_TOOLS,
            retriever=retriever,
        )

        eligibility_result = run_worker(
            "eligibility",
            eligibility_brief,
            model_call,
            eligibility_toolset,
            budgets,
        )

        record(
            "manager",
            "eligibility",
            eligibility_brief,
            eligibility_result,
            # The whole brief is re-sent context: the
            # question again, plus a report the
            # manager already holds.
            resent=estimate_tokens(
                eligibility_brief
            ),
        )

        worker_reports.append(
            summarise_for_manager(
                "eligibility",
                eligibility_result,
            )
        )

    # ---- hand-off 3: workers -> manager ----------
    #
    # The synthesis call. Every worker report is sent
    # again, on top of the question, which is the
    # third time the question has been paid for.
    synthesis_brief = (
        f"QUESTION:\n{question}\n\n"
        "SPECIALIST REPORTS:\n"
        f"{json.dumps(worker_reports, indent=2)}\n\n"
    )

    if failures:

        synthesis_brief += (
            "FAILED SPECIALISTS:\n"
            f"{json.dumps(failures, indent=2)}\n\n"
        )

    synthesis_brief += "Return JSON only."

    synthesis_started = time.monotonic()

    response = model_call(
        MANAGER_PROMPT,
        [
            {
                "role": "user",
                "content": synthesis_brief,
            }
        ],
        None,
        worker="manager",
    )

    synthesis_seconds = (
        time.monotonic() - synthesis_started
    )

    record(
        "workers",
        "manager",
        "synthesis",
        {
            "usage": {
                "input_tokens": response.get(
                    "input_tokens",
                    0,
                ),
                "output_tokens": response.get(
                    "output_tokens",
                    0,
                ),
            },
            "seconds": synthesis_seconds,
        },
        resent=estimate_tokens(
            synthesis_brief
        ),
    )

    final = parse_final(response.get("text"))

    return {
        "system": "orchestrator",
        "question": question,
        "answer": final["answer"],
        "value": final["value"],
        "sources": final["sources"],
        "iterations": len(log.entries),
        "terminated_by": None,
        "usage": usage.as_dict(),
        "seconds": round(
            time.monotonic() - started,
            3,
        ),
        "handoffs": log.as_dicts(),
        "handoff_log": log.lines(),
        "resent_tokens": log.resent_tokens,
        "failures": failures,
        "steps": [],
        "log": log.lines(),
    }


# Imported late to keep this module importable with
# no evaluation package present; the estimate is the
# same one the Week-8 harness uses, so the two weeks'
# token columns are on one scale.
def estimate_tokens(text: str) -> int:

    return max(
        1,
        -(-len(text or "") // 4),
    )
