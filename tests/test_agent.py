import json

from app.agent.loop import (
    Budgets,
    Usage,
    over_budget,
    parse_final,
    run_agent,
)
from app.agent.tools import (
    TOOL_SCHEMAS,
    call_tool,
    get_employee_record,
    get_jurisdiction_rules,
)
from app.agent.workflow import (
    find_employee_id,
)


def final_stub(
    instructions,
    items,
    tools,
) -> dict:

    return {
        "tool_calls": [],
        "text": json.dumps(
            {
                "answer": "Seven days.",
                "value": "7",
                "sources": [],
            }
        ),
        "input_tokens": 500,
        "output_tokens": 20,
    }


def one_tool_then_answer():
    """
    Calls a tool once, then answers - the shape a
    healthy run has.
    """

    state = {"called": False}

    def model_call(
        instructions,
        items,
        tools,
    ) -> dict:

        if state["called"]:
            return final_stub(
                instructions,
                items,
                tools,
            )

        state["called"] = True

        return {
            "tool_calls": [
                {
                    "call_id": "c1",
                    "name": (
                        "get_employee_record"
                    ),
                    "arguments": {
                        "employee_id": "E-1002"
                    },
                }
            ],
            "text": None,
            "input_tokens": 800,
            "output_tokens": 40,
        }

    return model_call


def never_stops(
    instructions,
    items,
    tools,
) -> dict:

    return {
        "tool_calls": [
            {
                "call_id": "c",
                "name": "get_employee_record",
                "arguments": {
                    "employee_id": "E-1002"
                },
            }
        ],
        "text": None,
        "input_tokens": 1000,
        "output_tokens": 50,
    }


# ---------------- tools ----------------


def test_record_flags_two_years_of_service():

    assert (
        get_employee_record("E-1001")[
            "has_two_years_service"
        ]
        is True
    )

    assert (
        get_employee_record("E-1002")[
            "has_two_years_service"
        ]
        is False
    )


def test_unknown_employee_returns_an_error():

    assert "error" in get_employee_record(
        "E-9999"
    )


def test_jurisdiction_rules_differ_by_region():

    uk = get_jurisdiction_rules("UK")

    india = get_jurisdiction_rules("India")

    assert (
        uk["notice_days_under_2_years"]
        != india["notice_days_under_2_years"]
    )


def test_unknown_jurisdiction_returns_an_error():

    assert "error" in get_jurisdiction_rules(
        "Atlantis"
    )


def test_call_tool_rejects_an_unknown_tool():

    assert "error" in call_tool(
        "delete_everything",
        {},
    )


def test_call_tool_reports_bad_arguments():

    assert "error" in call_tool(
        "get_employee_record",
        {"wrong_name": "E-1001"},
    )


def test_the_third_tool_uses_an_enum():

    schema = next(
        item
        for item in TOOL_SCHEMAS
        if item["name"]
        == "get_jurisdiction_rules"
    )

    parameter = schema["parameters"][
        "properties"
    ]["jurisdiction"]

    assert parameter["enum"] == [
        "UK",
        "India",
        "US",
    ]


def test_tool_descriptions_do_not_overlap():
    """
    Each tool names its own single source and
    disclaims the other two, because an overlapping
    description is what makes a model pick wrongly.
    """

    descriptions = {
        item["name"]: item["description"]
        for item in TOOL_SCHEMAS
    }

    assert (
        "Does not return policy text"
        in descriptions[
            "get_employee_record"
        ]
    )

    assert (
        "Knows nothing about any individual "
        "employee"
        in descriptions["search_handbook"]
    )

    assert (
        "does not look up employees"
        in descriptions[
            "get_jurisdiction_rules"
        ]
    )


# ---------------- budgets ----------------


def test_every_budget_is_checked():

    usage = Usage()

    usage.add(50_000, 0)

    assert (
        over_budget(
            Budgets(max_iterations=3),
            Usage(),
            3,
            0.0,
        )
        == "max_iterations"
    )

    assert (
        over_budget(
            Budgets(max_tokens=1_000),
            usage,
            0,
            9e18,
        )
        == "max_tokens"
    )


def test_wall_clock_budget_fires():
    """
    A start time far in the past is already over
    any wall-clock budget.
    """

    assert (
        over_budget(
            Budgets(max_seconds=1.0),
            Usage(),
            0,
            -1e6,
        )
        == "max_seconds"
    )


def test_nothing_fires_inside_budget():

    assert (
        over_budget(
            Budgets(),
            Usage(),
            0,
            9e18,
        )
        is None
    )


def test_a_runaway_loop_terminates_on_iterations():

    result = run_agent(
        "What notice must E-1002 give?",
        never_stops,
        Budgets(
            max_iterations=3,
            max_tokens=1_000_000,
            max_cost_usd=0.0,
            max_seconds=600,
        ),
    )

    assert (
        result["terminated_by"]
        == "max_iterations"
    )

    assert result["iterations"] == 3


def test_a_runaway_loop_terminates_on_tokens():

    result = run_agent(
        "What notice must E-1002 give?",
        never_stops,
        Budgets(
            max_iterations=50,
            max_tokens=2_000,
            max_cost_usd=0.0,
            max_seconds=600,
        ),
    )

    assert (
        result["terminated_by"] == "max_tokens"
    )

    assert result["iterations"] < 50


# ---------------- the loop ----------------


def test_tokens_are_summed_across_laps():
    """
    The loop re-sends the whole message list every
    lap, so a single lap's count understates the
    cost.
    """

    result = run_agent(
        "What notice must E-1002 give?",
        one_tool_then_answer(),
    )

    assert result["usage"]["calls"] == 2

    assert (
        result["usage"]["total_tokens"]
        == 800 + 40 + 500 + 20
    )


def test_the_loop_logs_every_step():

    result = run_agent(
        "What notice must E-1002 give?",
        one_tool_then_answer(),
    )

    kinds = [
        step["kind"]
        for step in result["steps"]
    ]

    assert "tool_call" in kinds
    assert "observation" in kinds
    assert "answer" in kinds


def test_the_loop_returns_the_parsed_value():

    result = run_agent(
        "What notice must E-1002 give?",
        one_tool_then_answer(),
    )

    assert result["value"] == "7"
    assert result["terminated_by"] is None


def test_non_json_output_still_returns_an_answer():

    parsed = parse_final("not json at all")

    assert parsed["answer"] == "not json at all"
    assert parsed["value"] is None


# ---------------- workflow ----------------


def test_workflow_finds_an_employee_id():

    assert (
        find_employee_id(
            "What notice must E-1002 give?"
        )
        == "E-1002"
    )


def test_workflow_handles_a_missing_id():

    assert (
        find_employee_id(
            "What is the leave policy?"
        )
        is None
    )


def echo_notice_stub(
    instructions,
    items,
    tools,
) -> dict:
    """
    Returns whatever notice figure the workflow
    computed, so the branch logic can be checked
    without a model.
    """

    payload = items[0]["content"]

    facts = json.loads(
        payload.split("FACTS:")[1].split(
            "Return JSON only."
        )[0]
    )

    days = facts.get(
        "applicable_notice_days"
    )

    return {
        "tool_calls": [],
        "text": json.dumps(
            {
                "answer": "stub",
                "value": (
                    str(days)
                    if days is not None
                    else None
                ),
                "sources": [],
            }
        ),
        "input_tokens": 0,
        "output_tokens": 0,
    }


def test_the_tenure_branch_picks_the_right_notice():
    """
    The dependent step: which notice figure applies
    cannot be known until tenure has been read.
    Same jurisdiction, opposite branches.
    """

    from app.agent.workflow import run_workflow

    cases = {
        "E-1002": "7",
        "E-1001": "30",
        "E-1004": "15",
        "E-1005": "14",
        "E-1006": "7",
    }

    for employee_id, expected in cases.items():

        result = run_workflow(
            f"What notice period must "
            f"{employee_id} give?",
            echo_notice_stub,
        )

        assert result["value"] == expected, (
            f"{employee_id} expected "
            f"{expected}, got {result['value']}"
        )
