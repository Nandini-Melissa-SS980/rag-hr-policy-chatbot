"""
The agent's tools.

Each description names exactly one job and says what
the tool does not do, because overlapping
descriptions - not the model - are the usual cause
of a tool being called for the wrong step.

    get_employee_record   - facts about a person
    search_handbook       - prose from the policies
    get_jurisdiction_rules- statutory figures by region

None of the three reads another's data source.
"""

import copy
import json
import os
from dataclasses import dataclass
from functools import lru_cache

from app.config import BASE_DIR


EMPLOYEES_PATH = os.path.join(
    BASE_DIR,
    "data",
    "employees.json",
)

JURISDICTIONS = [
    "UK",
    "India",
    "US",
]

TENURE_THRESHOLD_MONTHS = 24

HANDBOOK_TOP_K = 3


@lru_cache(maxsize=1)
def load_fixture() -> dict:

    with open(
        EMPLOYEES_PATH,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


@lru_cache(maxsize=1)
def get_retriever():
    """
    Imported here rather than at the top of the
    module so that the two tools that read JSON can
    be loaded - and evaluated - on a machine without
    the embedding stack installed. Nothing about the
    retrieval path changes.
    """

    from app.services.retriever import Retriever

    return Retriever("structure_aware")


def get_employee_record(
    employee_id: str,
) -> dict:
    """
    One employee's stored record.
    """

    employees = load_fixture()["employees"]

    record = employees.get(employee_id)

    if record is None:

        return {
            "error": (
                f"No employee record for "
                f"{employee_id}."
            )
        }

    # A copy, not the fixture. This tool reads; it
    # has no write path, and nothing downstream can
    # reach the stored record through its result.
    return {
        **copy.deepcopy(record),
        "has_two_years_service": (
            record["tenure_months"]
            >= TENURE_THRESHOLD_MONTHS
        ),
    }


def search_handbook(
    query: str,
) -> dict:
    """
    Policy passages matching a query.
    """

    results = get_retriever().retrieve(
        query,
        top_k=HANDBOOK_TOP_K,
    )

    return {
        "query": query,
        "passages": [
            {
                "policy_id": result[
                    "metadata"
                ].get("policy_id"),
                "section": result[
                    "metadata"
                ].get("section"),
                "score": round(
                    result["score"],
                    4,
                ),
                "text": result["text"],
            }
            for result in results
        ],
    }


def get_jurisdiction_rules(
    jurisdiction: str,
) -> dict:
    """
    Statutory figures for one jurisdiction.
    """

    rules = load_fixture()[
        "jurisdiction_rules"
    ]

    if jurisdiction not in rules:

        return {
            "error": (
                f"Unknown jurisdiction "
                f"{jurisdiction}. Expected one "
                f"of {', '.join(JURISDICTIONS)}."
            )
        }

    return rules[jurisdiction]


# The schemas the model sees. The description is the
# only thing steering tool choice, so each one is
# written to exclude the other two.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": "get_employee_record",
        "description": (
            "Look up one employee's stored record "
            "by employee id, returning their "
            "jurisdiction, tenure in months, "
            "employment type, and whether they "
            "have two years of service. Reads the "
            "employee database only. Does not "
            "return policy text and does not "
            "return statutory figures."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {
                    "type": "string",
                    "description": (
                        "Employee id, for example "
                        "E-1001."
                    ),
                }
            },
            "required": ["employee_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_handbook",
        "description": (
            "Search the company HR policy "
            "documents for passages matching a "
            "natural-language query, returning "
            "the policy text with its policy id "
            "and section. Reads the policy "
            "documents only. Knows nothing about "
            "any individual employee and returns "
            "no statutory figures."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "What to look for in the "
                        "policy text, for example "
                        "'notice period on "
                        "resignation'."
                    ),
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_jurisdiction_rules",
        "description": (
            "Return the statutory minimum notice "
            "periods and minimum annual leave for "
            "one jurisdiction, as a fixed table "
            "lookup. Notice is given separately "
            "for under two years of service and "
            "for two years or more, so the "
            "caller must already know the "
            "employee's tenure to pick the right "
            "figure. Reads the statutory table "
            "only. Does not search policy text "
            "and does not look up employees."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "jurisdiction": {
                    "type": "string",
                    "enum": JURISDICTIONS,
                    "description": (
                        "Which jurisdiction's "
                        "statutory table to read."
                    ),
                }
            },
            "required": ["jurisdiction"],
            "additionalProperties": False,
        },
    },
]


TOOLS = {
    "get_employee_record": get_employee_record,
    "search_handbook": search_handbook,
    "get_jurisdiction_rules": (
        get_jurisdiction_rules
    ),
}


def call_tool(
    name: str,
    arguments: dict,
) -> dict:

    tool = TOOLS.get(name)

    if tool is None:

        return {
            "error": f"No such tool: {name}."
        }

    try:
        return tool(**arguments)

    except TypeError as error:

        return {
            "error": (
                f"Bad arguments for {name}: "
                f"{error}"
            )
        }


# ---------------------------------------------------
# Week 8 additions
#
# Two switches, both off by default, so the path
# through this module with no arguments is the one
# Week 7 measured. The trajectory eval runs both
# arms in one process, and a default-off switch is
# the only way the ruler stays still between them.
#
#   build_toolset(validate_tenure=True)
#       The single mitigation.
#       get_jurisdiction_rules stops serving callers
#       that cannot say what the tenure is.
#
#   build_toolset(sanitise=True)
#       The injection defence. Free text inside a
#       tool result is stripped and labelled as data
#       before the model reads it.
# ---------------------------------------------------


# A tenure this system will accept as real. Above
# this, a caller is not reporting a fact, it is
# filling in a required field.
MAX_TENURE_MONTHS = 600


# Named so that "this agent cannot write" is
# checkable rather than assumed. Every tool here is
# a read; there is no mutating tool to scope down,
# and a test pins that this table stays empty.
WRITE_TOOLS: tuple = ()


def get_jurisdiction_rules_checked(
    jurisdiction: str,
    tenure_months=None,
) -> dict:
    """
    The mitigated statutory table.

    Same figures, same source, one new rule: a caller
    that cannot state the employee's tenure does not
    get the table.

    The point of this table is that it holds two
    notice figures and the tenure decides which one
    applies. A caller without the tenure was always
    guessing; requiring the number makes the guess
    fail loudly instead of returning a figure that
    happens to be right.
    """

    if tenure_months is None:

        return {
            "error": (
                "tenure_months is required. Read "
                "the employee's record with "
                "get_employee_record first and "
                "pass the tenure_months it "
                "returns."
            )
        }

    try:
        months = int(tenure_months)

    except (TypeError, ValueError):

        return {
            "error": (
                "tenure_months must be a whole "
                "number of months, not "
                f"{tenure_months!r}."
            )
        }

    if not 0 <= months <= MAX_TENURE_MONTHS:

        return {
            "error": (
                f"tenure_months {months} is "
                "outside the plausible range "
                f"0-{MAX_TENURE_MONTHS}."
            )
        }

    rules = get_jurisdiction_rules(jurisdiction)

    if "error" in rules:
        return rules

    # Echoed back so the trace records the number
    # the caller claimed, which is what makes a
    # fabricated tenure visible afterwards.
    return {
        **rules,
        "tenure_months_supplied": months,
    }


def checked_rules_schema() -> dict:
    """
    The mitigated schema: the base one with the
    dependency added as a required argument.
    """

    base = next(
        schema
        for schema in TOOL_SCHEMAS
        if schema["name"]
        == "get_jurisdiction_rules"
    )

    schema = copy.deepcopy(base)

    schema["description"] = base[
        "description"
    ] + (
        " Requires tenure_months, which must be "
        "read from the employee's record first; "
        "the call is refused without it."
    )

    schema["parameters"]["properties"][
        "tenure_months"
    ] = {
        "type": "integer",
        "description": (
            "The employee's tenure in months, as "
            "returned by get_employee_record. "
            "Required."
        ),
    }

    schema["parameters"]["required"] = [
        "jurisdiction",
        "tenure_months",
    ]

    return schema


def sanitise_result(
    name: str,
    result: dict,
) -> tuple:
    """
    Clean the free text out of one tool result.

    Only two fields in this system carry text that
    someone outside the system wrote: a manager's
    comment on a record, and the policy passages
    themselves. Both are treated the same way.
    """

    from app.agent.guardrails import (
        sanitise_free_text,
    )

    fired = []

    if not isinstance(result, dict):
        return result, fired

    cleaned = copy.deepcopy(result)

    if name == "get_employee_record":

        if "manager_comment" in cleaned:

            text, flags = sanitise_free_text(
                cleaned["manager_comment"]
            )

            cleaned["manager_comment"] = text

            fired.extend(flags)

    if name == "search_handbook":

        for passage in cleaned.get(
            "passages",
            [],
        ):

            text, flags = sanitise_free_text(
                passage.get("text", "")
            )

            passage["text"] = text

            fired.extend(flags)

    return cleaned, fired


@dataclass
class Toolset:
    """
    The schemas the model is offered and the
    functions behind them, bound together so an arm
    of the eval cannot offer one version's schema
    and then call the other version's function.
    """

    name: str

    schemas: list

    functions: dict

    sanitise: bool = False

    def call(
        self,
        name: str,
        arguments: dict,
    ) -> dict:

        tool = self.functions.get(name)

        if tool is None:

            return {
                "error": f"No such tool: {name}."
            }

        try:
            result = tool(**arguments)

        except TypeError as error:

            return {
                "error": (
                    f"Bad arguments for {name}: "
                    f"{error}"
                )
            }

        if self.sanitise:

            result, fired = sanitise_result(
                name,
                result,
            )

            if fired:

                result = {
                    **result,
                    "_sanitised": fired,
                }

        return result


def build_toolset(
    validate_tenure: bool = False,
    sanitise: bool = False,
    retriever=None,
) -> Toolset:
    """
    The toolset for one arm of the eval.

    `retriever` is injected so the handbook tool can
    be pointed either at the real index or, on a
    machine without the embedding model, at the
    frozen index read out of the Chroma file.
    """

    schemas = [
        copy.deepcopy(schema)
        for schema in TOOL_SCHEMAS
    ]

    functions = dict(TOOLS)

    if retriever is not None:

        def search_handbook_with(
            query: str,
        ) -> dict:

            results = retriever.retrieve(
                query,
                top_k=HANDBOOK_TOP_K,
            )

            return {
                "query": query,
                "passages": [
                    {
                        "policy_id": result[
                            "metadata"
                        ].get("policy_id"),
                        "section": result[
                            "metadata"
                        ].get("section"),
                        "score": round(
                            result["score"],
                            4,
                        ),
                        "text": result["text"],
                    }
                    for result in results
                ],
            }

        functions["search_handbook"] = (
            search_handbook_with
        )

    if validate_tenure:

        schemas = [
            checked_rules_schema()
            if schema["name"]
            == "get_jurisdiction_rules"
            else schema
            for schema in schemas
        ]

        functions[
            "get_jurisdiction_rules"
        ] = get_jurisdiction_rules_checked

    return Toolset(
        name=(
            "validated"
            if validate_tenure
            else "baseline"
        ),
        schemas=schemas,
        functions=functions,
        sanitise=sanitise,
    )
