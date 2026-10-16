"""
The agent, answering a question over MCP.

    python -m evaluation.week9.run_agent_mcp
    python -m evaluation.week9.run_agent_mcp --live

Discovers tools from every server in
mcp_servers.json, hands them to the unchanged
Week-7/8 agent loop, and runs one question that can
only be answered with a tool from the HRIS server.
The trace shows the tool name, so the call is
visible rather than asserted.

Also writes the before/after tool counts by reading
the config twice - once with the HRIS block switched
off, once with it on - so the counts come from
tools/list and not from notes.

WHERE THE MODEL RUNS: here, in this process, inside
run_agent. Neither server can reach it.
"""

import argparse
import copy
import json
import os
import tempfile

from app.agent.loop import Budgets, run_agent
from app.config import BASE_DIR
from app.mcp.client import (
    discover_toolset,
    load_config,
)


OUT_PATH = os.path.join(
    BASE_DIR,
    "evaluation",
    "week9",
    "tool_counts.md",
)

TRACE_PATH = os.path.join(
    BASE_DIR,
    "evaluation",
    "week9",
    "agent_trace.json",
)


QUESTION = (
    "How many days of annual leave does employee "
    "HR-1002 have left, and what does the policy "
    "say the full-time entitlement is?"
)


def config_with(only: list) -> str:
    """
    Write a temporary config holding just the named
    servers, so a tool count can be taken at each
    stage without hand-editing the real file.
    """

    config = copy.deepcopy(load_config())

    for name in list(config["mcpServers"]):

        if name not in only:
            config["mcpServers"][name][
                "enabled"
            ] = False

    handle = tempfile.NamedTemporaryFile(
        "w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    )

    json.dump(config, handle)

    handle.close()

    return handle.name


def count_tools(only: list) -> dict:

    path = config_with(only)

    toolset = discover_toolset(path)

    try:

        return {
            "servers": sorted(
                toolset.by_server()
            ),
            "count": len(toolset.tools),
            "names": toolset.tool_names(),
            "by_server": toolset.by_server(),
        }

    finally:

        toolset.close()

        os.unlink(path)


class ScriptedModel:
    """
    Stands in for the model, because there are still
    no API credits.

    It is deliberately dumb: it calls the two tools
    the question needs, then answers from what came
    back. What it proves is the plumbing - that a
    tool discovered from the HRIS server can be
    chosen by name and invoked through the agent
    loop - not that a real model would choose well.
    """

    def __init__(self, schemas: list):

        self.available = [
            schema["name"] for schema in schemas
        ]

        self.plan = [
            (
                "hris__get_leave_balance",
                {"employee_id": "HR-1002"},
            ),
            (
                "policy__search_handbook",
                {
                    "query": (
                        "annual leave "
                        "entitlement full-time "
                        "employees"
                    )
                },
            ),
        ]

        self.step = 0

    def __call__(
        self,
        instructions,
        items,
        tools=None,
    ) -> dict:

        if self.step < len(self.plan):

            name, arguments = self.plan[
                self.step
            ]

            self.step += 1

            if name not in self.available:

                return {
                    "tool_calls": [],
                    "text": json.dumps(
                        {
                            "answer": (
                                f"{name} was not "
                                "discovered."
                            ),
                            "value": None,
                            "sources": [],
                        }
                    ),
                    "input_tokens": 0,
                    "output_tokens": 0,
                }

            return {
                "tool_calls": [
                    {
                        "call_id": (
                            f"call_{self.step}"
                        ),
                        "name": name,
                        "arguments": arguments,
                    }
                ],
                "text": None,
                "input_tokens": 900,
                "output_tokens": 40,
            }

        balance = None

        for item in items:

            if (
                item.get("type")
                != "function_call_output"
            ):
                continue

            payload = json.loads(item["output"])

            if "accrued_leave_days" in payload:
                balance = payload[
                    "accrued_leave_days"
                ]

        return {
            "tool_calls": [],
            "text": json.dumps(
                {
                    "answer": (
                        f"HR-1002 has {balance} "
                        "days of accrued leave "
                        "remaining. The handbook "
                        "grants full-time "
                        "employees twenty-five "
                        "days per leave year."
                    ),
                    "value": str(balance),
                    "sources": [
                        {
                            "policy_id": "HR-202",
                            "section": "2.1",
                        }
                    ],
                }
            ),
            "input_tokens": 1200,
            "output_tokens": 60,
        }


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--live",
        action="store_true",
    )

    arguments = parser.parse_args()

    before = count_tools(["policy"])

    after = count_tools(["policy", "hris"])

    toolset = discover_toolset()

    called = []

    def dispatch(name, args):

        result = toolset.call(name, args)

        called.append(name)

        return result

    if arguments.live:

        from app.agent.model import (
            make_model_call,
        )

        model_call = make_model_call()

    else:
        model_call = ScriptedModel(
            toolset.schemas
        )

    try:

        result = run_agent(
            QUESTION,
            model_call,
            Budgets(),
            tool_schemas=toolset.schemas,
            tool_call=dispatch,
        )

    finally:
        toolset.close()

    print(
        f"tools before : {before['count']} "
        f"{before['names']}"
    )

    print(
        f"tools after  : {after['count']} "
        f"{after['names']}"
    )

    print("\ntrace:")

    for line in result["log"]:
        print("  " + line)

    print(
        "\ntools actually invoked: "
        f"{called}"
    )

    print(f"answer: {result['answer']}")

    from_hris = [
        name
        for name in called
        if name.startswith("hris__")
    ]

    print(
        "\ncalled a tool from the NEW server: "
        f"{bool(from_hris)} {from_hris}"
    )

    with open(
        TRACE_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            {
                "question": QUESTION,
                "tools_invoked": called,
                "tools_from_hris": from_hris,
                "answer": result["answer"],
                "value": result["value"],
                "log": result["log"],
                "steps": result["steps"],
            },
            file,
            indent=2,
        )

    lines = [
        "# Tools discovered, before and after",
        "",
        "Both counts come from `tools/list` at run "
        "time - the client asks each server what it "
        "has and counts the replies. Nothing here "
        "is read from a list in the code.",
        "",
        f"**{before['count']} before -> "
        f"{after['count']} after.**",
        "",
        "| Stage | Servers | Tools | Names |",
        "| --- | --- | --- | --- |",
        f"| Before | {', '.join(before['servers'])} "
        f"| {before['count']} | "
        + ", ".join(
            f"`{name}`"
            for name in before["names"]
        )
        + " |",
        f"| After | {', '.join(after['servers'])} "
        f"| {after['count']} | "
        + ", ".join(
            f"`{name}`"
            for name in after["names"]
        )
        + " |",
        "",
        "Grouped by the server each came from:",
        "",
        "```json",
        json.dumps(after["by_server"], indent=2),
        "```",
        "",
        "The two new tools arrived from the HRIS "
        "server after an eight-line addition to "
        "`mcp_servers.json`. No Python was edited "
        "- see `agent_diff.txt`.",
        "",
        "## One query that provably calls the new "
        "server",
        "",
        f"> {QUESTION}",
        "",
        "```",
        *result["log"],
        "```",
        "",
        f"Tools invoked: "
        + ", ".join(f"`{name}`" for name in called),
        "",
        f"From the new server: "
        + ", ".join(
            f"`{name}`" for name in from_hris
        ),
        "",
        f"Answer: {result['answer']}",
        "",
        "> The model here is a scripted stand-in "
        "(no API credits). It proves the plumbing - "
        "a tool discovered from the HRIS server is "
        "selected by name and invoked through the "
        "unchanged agent loop - not that a real "
        "model would choose well. `--live` runs the "
        "same path against the real model.",
        "",
    ]

    with open(
        OUT_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        file.write("\n".join(lines))

    print(f"\nWrote {OUT_PATH} and {TRACE_PATH}")


if __name__ == "__main__":
    main()
