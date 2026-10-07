"""
What the MCP layer must not get wrong.

The load-bearing claim of this week is that adding a
server needs no agent change. These tests pin the
things that would quietly make that false: a client
that knows a tool's name, an agent that imports MCP,
a server that reaches for a model, and a credential
handed to a third party.

The discovery tests start real subprocesses, so they
are slower than the rest of the suite and are marked
so they can be deselected.
"""

import json
import os

import pytest

from app.mcp.client import (
    PASSTHROUGH,
    child_environment,
    enabled_servers,
    load_config,
    to_openai_schema,
    unwrap,
)


ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)


# ---------------- config ----------------


def test_the_config_lists_both_servers():

    servers = enabled_servers(load_config())

    assert "policy" in servers

    assert "hris" in servers


def test_a_server_can_be_switched_off():
    """
    Discovery reads `enabled`, so a before-and-after
    count can be taken without deleting the block.
    """

    config = {
        "mcpServers": {
            "on": {"command": "x"},
            "off": {
                "command": "y",
                "enabled": False,
            },
        }
    }

    assert set(enabled_servers(config)) == {
        "on"
    }


# ---------------- no hard-coding ----------------


def test_the_client_names_no_tool():
    """
    The point of the week. If the client mentions a
    tool or a server by name, discovery is a
    decoration and adding a server would mean
    editing Python.
    """

    with open(
        os.path.join(
            ROOT,
            "app",
            "mcp",
            "client.py",
        ),
        encoding="utf-8",
    ) as file:

        source = file.read()

    for name in [
        "search_handbook",
        "get_policy_version",
        "get_leave_balance",
        "get_grade_band",
    ]:

        assert f'"{name}"' not in source, (
            f"client.py hard-codes {name}"
        )


def test_the_agent_does_not_import_mcp():
    """
    The agent must not learn what MCP is. If it
    imports the client, the zero-line diff was luck.
    """

    agent = os.path.join(ROOT, "app", "agent")

    for entry in os.listdir(agent):

        if not entry.endswith(".py"):
            continue

        with open(
            os.path.join(agent, entry),
            encoding="utf-8",
        ) as file:

            source = file.read()

        assert "app.mcp" not in source, (
            f"{entry} imports the MCP client"
        )

        assert "import mcp" not in source, (
            f"{entry} imports the MCP SDK"
        )


def test_no_server_can_reach_the_model():
    """
    The architecture mistake the brief calls out:
    an LLM call inside the server. The host runs the
    model; a server exposes a capability.
    """

    servers = os.path.join(ROOT, "mcp_servers")

    for entry in os.listdir(servers):

        if not entry.endswith(".py"):
            continue

        with open(
            os.path.join(servers, entry),
            encoding="utf-8",
        ) as file:

            source = file.read()

        for forbidden in [
            "from openai",
            "import openai",
            "OPENAI_API_KEY",
            "make_model_call",
        ]:

            assert forbidden not in source, (
                f"{entry} reaches for the model "
                f"via {forbidden}"
            )


# ---------------- least privilege ----------------


def test_the_model_key_is_not_handed_to_a_server(
    monkeypatch,
):
    """
    A server is a subprocess and would inherit the
    whole environment. A third-party HRIS connector
    has no use for our model key.
    """

    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "sk-canary",
    )

    environment = child_environment({})

    assert (
        "OPENAI_API_KEY" not in environment
    )


def test_a_server_still_gets_what_it_declares():

    environment = child_environment(
        {"env": {"HRIS_SCOPES": "hris:leave"}}
    )

    assert (
        environment["HRIS_SCOPES"]
        == "hris:leave"
    )


def test_a_server_can_still_run(monkeypatch):

    monkeypatch.setenv("PATH", "/usr/bin")

    assert "PATH" in child_environment({})

    assert "PATH" in PASSTHROUGH


# ---------------- schema translation ----------------


class FakeTool:

    def __init__(
        self,
        name,
        description,
        schema,
    ):

        self.name = name

        self.description = description

        self.input_schema = schema


def test_a_tool_is_namespaced_by_its_server():
    """
    Two servers may both expose a `search`. The
    dispatcher has to know which process to send the
    call to.
    """

    schema = to_openai_schema(
        FakeTool(
            "search",
            "Find things.",
            {"type": "object"},
        ),
        "policy",
    )

    assert (
        schema["name"] == "policy__search"
    )


def test_the_docstring_becomes_the_description():
    """
    The docstring is the prompt the model reads.
    """

    schema = to_openai_schema(
        FakeTool(
            "x",
            "  Use this when asked about leave.  ",
            {"type": "object"},
        ),
        "hris",
    )

    assert (
        schema["description"]
        == "Use this when asked about leave."
    )


def test_a_tool_without_a_schema_still_works():

    schema = to_openai_schema(
        FakeTool("x", "y", None),
        "s",
    )

    assert (
        schema["parameters"]["type"]
        == "object"
    )


# ---------------- results ----------------


class FakeBlock:

    def __init__(self, text):
        self.text = text


class FakeResult:

    def __init__(
        self,
        text,
        structured=None,
    ):

        self.content = [FakeBlock(text)]

        self.structured_content = structured


def test_a_json_payload_comes_back_as_a_dict():

    assert unwrap(
        FakeResult('{"days": 7}')
    ) == {"days": 7}


def test_plain_text_is_not_dropped():

    assert unwrap(FakeResult("hello")) == {
        "text": "hello"
    }


def test_a_recoverable_error_is_a_result_not_a_raise():
    """
    A business failure has to reach the model as
    something it can read. If it raised, the model
    would see a transport fault and could not
    recover.
    """

    payload = unwrap(
        FakeResult(
            json.dumps(
                {
                    "error": "unknown_employee",
                    "recoverable": True,
                }
            )
        )
    )

    assert payload["recoverable"] is True


# ---------------- the servers themselves ----------------


def test_the_hris_denies_a_scope_it_was_not_given(
    monkeypatch,
):

    monkeypatch.setenv(
        "HRIS_SCOPES",
        "hris:leave",
    )

    from mcp_servers import hris_server

    denied = json.loads(
        hris_server.get_grade_band(
            "HR-1001"
        )
    )

    assert denied["error"] == "scope_denied"

    assert denied["missing_scope"] == (
        "hris:grade"
    )

    # Recoverable, but explicitly not retryable -
    # the model must report the gap, not loop.
    assert denied["recoverable"] is True

    assert denied["retryable"] is False

    allowed = json.loads(
        hris_server.get_leave_balance(
            "HR-1001"
        )
    )

    assert "accrued_leave_days" in allowed


def test_an_unknown_id_explains_the_format(
    monkeypatch,
):
    """
    The model has to be able to tell a wrong id from
    an outage, and fix it.
    """

    monkeypatch.delenv(
        "HRIS_SCOPES",
        raising=False,
    )

    from mcp_servers import hris_server

    miss = json.loads(
        hris_server.get_leave_balance(
            "E-1002"
        )
    )

    assert miss["error"] == "unknown_employee"

    assert miss["expected_format"] == "HR-nnnn"

    assert "HR-1001" in miss["message"]


def test_a_date_before_the_index_is_recoverable():

    from mcp_servers import policy_server

    miss = json.loads(
        policy_server.get_policy_version(
            "2023-01-01"
        )
    )

    assert (
        miss["error"] == "no_version_effective"
    )

    assert miss["recoverable"] is True

    # It names what DOES exist, which is what makes
    # the next call possible.
    assert (
        miss["retry_with"]["effective_date"]
        == "2024-04-01"
    )


# ---------------- discovery, for real ----------------


@pytest.mark.slow
def test_discovery_finds_both_servers_tools():
    """
    Starts both servers over stdio and asks them.
    Slow, because it is the real handshake.
    """

    from app.mcp.client import discover_toolset

    toolset = discover_toolset()

    try:

        names = toolset.tool_names()

        assert len(names) == 4

        assert (
            "hris__get_leave_balance" in names
        )

        assert (
            "policy__search_handbook" in names
        )

        result = toolset.call(
            "hris__get_leave_balance",
            {"employee_id": "HR-1002"},
        )

        assert (
            result["accrued_leave_days"] == 7.0
        )

    finally:
        toolset.close()


@pytest.mark.slow
def test_an_undiscovered_tool_is_refused():

    from app.mcp.client import discover_toolset

    toolset = discover_toolset()

    try:

        result = toolset.call(
            "policy__delete_everything",
            {},
        )

        assert result["error"] == "unknown_tool"

    finally:
        toolset.close()
