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

import json
import os
from functools import lru_cache

from app.config import BASE_DIR
from app.services.retriever import Retriever


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
def get_retriever() -> Retriever:

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

    return {
        **record,
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
