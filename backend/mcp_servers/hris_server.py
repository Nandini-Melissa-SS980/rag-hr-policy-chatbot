"""
Server two: the HRIS, as People Ops shipped it.

    python -m mcp_servers.hris_server

Stands in for the third-party MCP server over the
HRIS. It is in this repo so the week can be run and
captured end to end, but it is written as an outside
system: its own store, its own id format, its own
error vocabulary, and a token it checks for itself.

Nothing in the agent knows this file exists. It is
reached only through mcp_servers.json.

WHERE THE MODEL RUNS: not here either. No API key, no
model client. See risk_note.md for what this process
can reach and what a stolen token would buy.

Scopes, for the gateway exercise:

    hris:leave   read accrued leave balance
    hris:grade   read grade band (salary-adjacent)

HRIS_SCOPES sets what this process will serve. Drop
hris:grade and get_grade_band starts refusing, in a
way the model can read and act on.
"""

import json
import os


from mcp.server.mcpserver import MCPServer


server = MCPServer(
    name="hris",
    instructions=(
        "Read-only view of the HRIS: grade band and "
        "accrued leave balance by employee id."
    ),
)


# Deliberately a different shape from the app's own
# E-1001 ids, because a real HRIS would not share an
# id scheme with a policy chatbot. The mismatch is
# the point of the recoverable error below.
EMPLOYEES = {
    "HR-1001": {
        "employee_id": "HR-1001",
        "grade_band": "G6",
        "accrued_leave_days": 18.5,
        "leave_year_ends": "2026-12-31",
    },
    "HR-1002": {
        "employee_id": "HR-1002",
        "grade_band": "G4",
        "accrued_leave_days": 7.0,
        "leave_year_ends": "2026-12-31",
    },
    "HR-1003": {
        "employee_id": "HR-1003",
        "grade_band": "G7",
        "accrued_leave_days": 24.0,
        "leave_year_ends": "2026-12-31",
    },
    "HR-1004": {
        "employee_id": "HR-1004",
        "grade_band": "G3",
        "accrued_leave_days": 2.5,
        "leave_year_ends": "2026-12-31",
    },
    "HR-1005": {
        "employee_id": "HR-1005",
        "grade_band": "G5",
        "accrued_leave_days": 11.0,
        "leave_year_ends": "2026-12-31",
    },
    "HR-1006": {
        "employee_id": "HR-1006",
        "grade_band": "G2",
        "accrued_leave_days": 1.0,
        "leave_year_ends": "2026-12-31",
    },
}


ALL_SCOPES = ("hris:leave", "hris:grade")


def granted_scopes() -> set:
    """
    What this process is allowed to serve.

    Read from the environment rather than baked in,
    so a narrower token can be handed to the server
    without editing it.
    """

    raw = os.environ.get("HRIS_SCOPES")

    if raw is None:
        return set(ALL_SCOPES)

    return {
        scope.strip()
        for scope in raw.split(",")
        if scope.strip()
    }


def denied(scope: str, tool: str) -> str:
    """
    A refusal the model can act on.

    It says which scope was missing and that retrying
    will not help, so the model reports the gap
    instead of looping on it or inventing a figure.
    """

    return json.dumps(
        {
            "error": "scope_denied",
            "message": (
                f"The HRIS token for this session "
                f"does not carry {scope!r}, which "
                f"{tool} requires. This will not "
                "succeed on retry. Answer from the "
                "policy handbook instead, and say "
                "that the HRIS field was not "
                "available."
            ),
            "missing_scope": scope,
            "recoverable": True,
            "retryable": False,
        }
    )


def unknown_employee(employee_id) -> str:
    """
    The id-format miss, told properly.

    "Not found" would leave the model unable to tell
    a wrong id from an HRIS outage. Naming the format
    lets it fix its own call.
    """

    return json.dumps(
        {
            "error": "unknown_employee",
            "message": (
                f"No HRIS record for "
                f"{employee_id!r}. HRIS ids look "
                "like HR-1001, not like the "
                "policy app's E-1001 ids. If you "
                "have an E-number, the HRIS id is "
                "the same digits with an HR "
                "prefix."
            ),
            "expected_format": "HR-nnnn",
            "known_ids": sorted(EMPLOYEES),
            "recoverable": True,
        }
    )


@server.tool()
def get_leave_balance(employee_id: str) -> str:
    """
    Read how many days of annual leave one employee
    has accrued and not yet taken.

    Use this when the question is about what this
    person has left, rather than what the policy
    grants everyone. The handbook gives the
    entitlement; only this gives the balance.

    Args:
        employee_id: HRIS id, formatted HR-nnnn, for
            example HR-1001.
    """

    if "hris:leave" not in granted_scopes():
        return denied(
            "hris:leave",
            "get_leave_balance",
        )

    record = EMPLOYEES.get(employee_id)

    if record is None:
        return unknown_employee(employee_id)

    return json.dumps(
        {
            "employee_id": record[
                "employee_id"
            ],
            "accrued_leave_days": record[
                "accrued_leave_days"
            ],
            "leave_year_ends": record[
                "leave_year_ends"
            ],
        }
    )


@server.tool()
def get_grade_band(employee_id: str) -> str:
    """
    Read one employee's grade band.

    Use this only when the question turns on
    seniority, such as which appraisal track or
    entitlement tier applies. The band is
    salary-adjacent, so do not read it to decorate an
    answer that does not need it.

    Args:
        employee_id: HRIS id, formatted HR-nnnn, for
            example HR-1001.
    """

    if "hris:grade" not in granted_scopes():
        return denied(
            "hris:grade",
            "get_grade_band",
        )

    record = EMPLOYEES.get(employee_id)

    if record is None:
        return unknown_employee(employee_id)

    return json.dumps(
        {
            "employee_id": record[
                "employee_id"
            ],
            "grade_band": record["grade_band"],
        }
    )


if __name__ == "__main__":
    server.run(transport="stdio")
