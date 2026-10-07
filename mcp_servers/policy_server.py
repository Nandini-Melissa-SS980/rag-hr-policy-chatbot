"""
Server one: the policy search this app already does.

    python -m mcp_servers.policy_server

An MCP server over stdio. It exposes the one thing
this app is actually good at - finding a passage in
the HR handbook - so that any host, not just this
repo's agent, can use it.

WHERE THE MODEL RUNS: not here. This process holds no
API key, imports no model client, and never calls one.
It answers tools/list and tools/call and nothing else.
The host runs the model and decides which tool to
call; this server only knows a tool was called.

Why the handbook search is a tool and the handbook
itself is not: a tool is invoked by the model when it
decides it needs one. A resource is attached by the
app before the model is asked anything. The full
handbook is context the app should hand over, so it
is not exposed here as a tool to be fetched - that
would spend a turn retrieving a document the host
could have supplied for free.
"""

import json

from mcp.server.mcpserver import MCPServer


server = MCPServer(
    name="policy",
    instructions=(
        "Search of the company HR policy handbook. "
        "Knows the policy text and nothing about "
        "any individual employee."
    ),
)


# The earliest handbook edition in the index. A
# request for a version before this is a miss with a
# knowable cause, not a fault - see get_policy_version.
EARLIEST_EFFECTIVE_DATE = "2024-04-01"


def load_retriever():
    """
    Imported lazily and cached by the app, so the
    embedding model is loaded once per server
    process rather than once per call.
    """

    from app.agent.tools import get_retriever

    return get_retriever()


@server.tool()
def search_handbook(query: str) -> str:
    """
    Find the passages of the company HR handbook that
    answer a question about company policy.

    Use this for what the company itself promises -
    leave entitlement, notice, remote working,
    promotion. Each passage comes back with the
    policy id and section number to cite.

    Do not use this for an individual's own record or
    for a statutory legal minimum: this searches the
    handbook text only and knows neither.

    Args:
        query: What to look for, in plain words, for
            example "how much notice on resignation"
            or "carrying leave into next year".
    """

    results = load_retriever().retrieve(
        query,
        top_k=3,
    )

    passages = [
        {
            "policy_id": result[
                "metadata"
            ].get("policy_id"),
            "section": result["metadata"].get(
                "section"
            ),
            "score": round(result["score"], 4),
            "text": result["text"],
        }
        for result in results
    ]

    if not passages:

        return json.dumps(
            {
                "query": query,
                "passages": [],
                "note": (
                    "No handbook passage matched. "
                    "The handbook covers "
                    "attendance, annual leave, "
                    "performance, flexible "
                    "working, promotion and "
                    "remote working. It does not "
                    "cover notice periods, which "
                    "are statutory."
                ),
            }
        )

    return json.dumps(
        {
            "query": query,
            "passages": passages,
        }
    )


@server.tool()
def get_policy_version(effective_date: str) -> str:
    """
    Find which edition of the handbook was in force
    on a given date.

    Use this before quoting a figure for anything
    historical - an appraisal or a dispute about last
    year - so the answer quotes the edition that
    actually applied then.

    Args:
        effective_date: The date the answer has to be
            correct for, as YYYY-MM-DD, for example
            "2024-06-01".
    """

    if not isinstance(effective_date, str) or (
        len(effective_date) != 10
        or effective_date[4] != "-"
        or effective_date[7] != "-"
    ):

        return json.dumps(
            {
                "error": "malformed_date",
                "message": (
                    f"effective_date "
                    f"{effective_date!r} is not a "
                    "date. Pass it as YYYY-MM-DD, "
                    "for example 2024-06-01."
                ),
            }
        )

    if effective_date < EARLIEST_EFFECTIVE_DATE:

        # A recoverable miss. The model is told what
        # is wrong, what does exist, and what to do
        # next - so it can re-ask rather than either
        # giving up or quoting a figure from an
        # edition it has no evidence for.
        return json.dumps(
            {
                "error": "no_version_effective",
                "message": (
                    "No policy version effective "
                    f"{effective_date}: the "
                    "earliest edition in the "
                    "index is "
                    f"{EARLIEST_EFFECTIVE_DATE}. "
                    "Nothing before that date has "
                    "been digitised, so no figure "
                    "can be quoted for it."
                ),
                "earliest_effective_date": (
                    EARLIEST_EFFECTIVE_DATE
                ),
                "recoverable": True,
                "retry_with": {
                    "effective_date": (
                        EARLIEST_EFFECTIVE_DATE
                    )
                },
            }
        )

    return json.dumps(
        {
            "effective_date": effective_date,
            "version": "2024.1",
            "in_force_since": (
                EARLIEST_EFFECTIVE_DATE
            ),
            "policies": [
                "HR-201",
                "HR-202",
                "HR-203",
                "HR-204",
                "HR-205",
                "HR-207",
            ],
        }
    )


if __name__ == "__main__":
    server.run(transport="stdio")
