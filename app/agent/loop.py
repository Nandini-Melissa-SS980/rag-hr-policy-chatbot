"""
The agent loop, hand built.

    plan -> call a tool -> read the result -> repeat

Four budgets are checked on every lap, not just
declared: iterations, tokens, cost, and wall clock.
Whichever trips first ends the run cleanly and is
named in `terminated_by`.

The model call is injected rather than imported, so
the loop's control flow can be tested with a stub
and does not depend on a live API.
"""

import json
import time
from dataclasses import dataclass, field

from app.agent.tools import (
    TOOL_SCHEMAS,
    call_tool,
)
from app.config import (
    INPUT_COST_PER_1M,
    OUTPUT_COST_PER_1M,
)


SYSTEM_PROMPT = """
You answer HR entitlement questions about a named
employee, using only the tools provided.

Work one step at a time. Look at each tool result
before deciding the next call.

Notice periods depend on length of service, so read
the employee's tenure before reading a jurisdiction's
statutory table.

When you have enough information, stop calling tools
and reply with JSON only:

{
  "answer": "one or two sentences",
  "value": "the single key figure, digits only where
            it is a number of days",
  "sources": [{"policy_id": "HR-201", "section": "3.1"}]
}

Use "value": null if the question has no single
figure. Cite a policy section only if you read it
from search_handbook.
"""


@dataclass
class Budgets:
    """
    All four are enforced. A budget that is never
    checked is a comment, not a limit.
    """

    max_iterations: int = 6
    max_tokens: int = 20_000
    max_cost_usd: float = 0.05
    max_seconds: float = 60.0


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def add(
        self,
        input_tokens: int,
        output_tokens: int,
    ):
        """
        Every lap re-sends the whole message list, so
        each lap's tokens are added rather than
        replaced.
        """

        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.calls += 1

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
        )

    @property
    def cost_usd(self) -> float:

        return (
            self.input_tokens
            / 1_000_000
            * INPUT_COST_PER_1M
            + self.output_tokens
            / 1_000_000
            * OUTPUT_COST_PER_1M
        )

    def as_dict(self) -> dict:

        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "calls": self.calls,
            "cost_usd": round(
                self.cost_usd,
                6,
            ),
        }


@dataclass
class Trace:
    """
    Every step, so the loop is never a black box.
    """

    steps: list = field(
        default_factory=list
    )

    def add(
        self,
        kind: str,
        detail: str,
    ):

        self.steps.append(
            {
                "step": len(self.steps) + 1,
                "kind": kind,
                "detail": detail,
            }
        )

    def lines(self) -> list[str]:

        return [
            f"[{step['step']:>2}] "
            f"{step['kind']:<12} "
            f"{step['detail']}"
            for step in self.steps
        ]


def over_budget(
    budgets: Budgets,
    usage: Usage,
    iterations: int,
    started: float,
) -> str | None:
    """
    The name of the first budget exceeded, or None.
    """

    if iterations >= budgets.max_iterations:
        return "max_iterations"

    if usage.total_tokens >= budgets.max_tokens:
        return "max_tokens"

    if (
        budgets.max_cost_usd > 0
        and usage.cost_usd
        >= budgets.max_cost_usd
    ):
        return "max_cost_usd"

    if (
        time.monotonic() - started
        >= budgets.max_seconds
    ):
        return "max_seconds"

    return None


def parse_final(text: str) -> dict:

    try:
        data = json.loads(text)

    except (json.JSONDecodeError, TypeError):

        return {
            "answer": text or "",
            "value": None,
            "sources": [],
        }

    return {
        "answer": data.get("answer", ""),
        "value": data.get("value"),
        "sources": data.get("sources", []),
    }


def run_agent(
    question: str,
    model_call,
    budgets: Budgets | None = None,
    tool_schemas: list | None = None,
    tool_call=None,
) -> dict:
    """
    The toolset is injected for the same reason the
    model is: the Week-8 trajectory eval runs a
    baseline arm and a mitigated arm in one process,
    and they must differ only in the tools, not in
    the loop. Both default to the module-level
    toolset, so calling this with two arguments is
    the Week-7 behaviour exactly.

    `model_call(instructions, items, tools)` returns

        {
          "tool_calls": [
            {"call_id", "name", "arguments"}
          ],
          "text": str | None,
          "input_tokens": int,
          "output_tokens": int,
        }
    """

    budgets = budgets or Budgets()

    schemas = (
        TOOL_SCHEMAS
        if tool_schemas is None
        else tool_schemas
    )

    dispatch = (
        call_tool
        if tool_call is None
        else tool_call
    )

    usage = Usage()

    trace = Trace()

    started = time.monotonic()

    items = [
        {
            "role": "user",
            "content": question,
        }
    ]

    final = None

    terminated_by = None

    iterations = 0

    while True:

        terminated_by = over_budget(
            budgets,
            usage,
            iterations,
            started,
        )

        if terminated_by:

            trace.add(
                "terminated",
                f"budget {terminated_by} reached "
                f"after {iterations} iteration(s)",
            )

            break

        iterations += 1

        trace.add(
            "think",
            f"lap {iterations}: asking the model "
            f"what to do next",
        )

        response = model_call(
            SYSTEM_PROMPT,
            items,
            schemas,
        )

        usage.add(
            response.get(
                "input_tokens",
                0,
            ),
            response.get(
                "output_tokens",
                0,
            ),
        )

        tool_calls = response.get(
            "tool_calls"
        ) or []

        if not tool_calls:

            final = parse_final(
                response.get("text")
            )

            trace.add(
                "answer",
                "model returned a final answer",
            )

            break

        for tool_call in tool_calls:

            name = tool_call["name"]

            arguments = tool_call.get(
                "arguments"
            ) or {}

            trace.add(
                "tool_call",
                f"{name}({json.dumps(arguments)})",
            )

            result = dispatch(
                name,
                arguments,
            )

            trace.add(
                "observation",
                json.dumps(result)[:200],
            )

            items.append(
                {
                    "type": "function_call",
                    "call_id": tool_call[
                        "call_id"
                    ],
                    "name": name,
                    "arguments": json.dumps(
                        arguments
                    ),
                }
            )

            items.append(
                {
                    "type": (
                        "function_call_output"
                    ),
                    "call_id": tool_call[
                        "call_id"
                    ],
                    "output": json.dumps(result),
                }
            )

    if final is None:

        final = {
            "answer": (
                "Stopped before reaching an "
                "answer."
            ),
            "value": None,
            "sources": [],
        }

    return {
        "system": "agent",
        "question": question,
        "answer": final["answer"],
        "value": final["value"],
        "sources": final["sources"],
        "iterations": iterations,
        "terminated_by": terminated_by,
        "usage": usage.as_dict(),
        "seconds": round(
            time.monotonic() - started,
            3,
        ),
        "steps": trace.steps,
        "log": trace.lines(),
    }
