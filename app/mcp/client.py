"""
The MCP client: tools discovered, not wired in.

    from app.mcp.client import discover_toolset
    toolset = discover_toolset()
    run_agent(question, model_call,
              tool_schemas=toolset.schemas,
              tool_call=toolset.call)

This is the host side. It reads mcp_servers.json,
starts each server it lists, asks every one of them
tools/list, and turns what comes back into the same
`Toolset` the Week-8 agent already takes. The agent
is handed schemas and a dispatcher; it cannot tell
whether they came from a Python function, one server
or four.

That is the whole claim of the week, and it is why
adding a server is a config edit. Nothing here names
a tool. Nothing here names a server. Add a block to
mcp_servers.json and the tool count goes up.

WHERE THE MODEL RUNS: in the host, above this file.
`run_agent` calls the model; this module only carries
tool descriptions up and tool calls down. No MCP
server in this repo can reach the model.
"""

import asyncio
import json
import os
import sys
import threading
from dataclasses import dataclass, field

from app.agent.tools import Toolset
from app.config import BASE_DIR


CONFIG_PATH = os.path.join(
    BASE_DIR,
    "mcp_servers.json",
)


def load_config(
    path: str = None,
) -> dict:

    with open(
        path or CONFIG_PATH,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


def enabled_servers(config: dict) -> dict:
    """
    The servers the config asks for, in file order.

    A server can be switched off with
    "enabled": false rather than deleted, so a
    before-and-after can be taken without losing the
    block.
    """

    return {
        name: spec
        for name, spec in config.get(
            "mcpServers",
            {},
        ).items()
        if spec.get("enabled", True)
    }


def to_openai_schema(
    tool,
    prefix: str,
) -> dict:
    """
    One MCP tool description, in the shape the
    model's tool-calling API expects.

    The name is prefixed with the server it came
    from, because two servers may legitimately both
    expose a `search`, and the dispatcher has to know
    which process to send the call to.

    The description is the server's own - this is
    where a tool docstring becomes the prompt the
    model reads.
    """

    # mcp 2.x renamed this to input_schema; 1.x
    # called it inputSchema. Both are read so this
    # host works against either SDK.
    schema = (
        getattr(tool, "input_schema", None)
        or getattr(tool, "inputSchema", None)
        or {
            "type": "object",
            "properties": {},
        }
    )

    return {
        "type": "function",
        "name": f"{prefix}__{tool.name}",
        "description": (
            tool.description or ""
        ).strip(),
        "parameters": schema,
    }


# Variables a tool server needs to be a working
# Python process on this machine, and nothing more.
# Everything else is withheld by default.
PASSTHROUGH = (
    "PATH",
    "SYSTEMROOT",
    "COMSPEC",
    "TEMP",
    "TMP",
    "PATHEXT",
    "PYTHONPATH",
    "PYTHONIOENCODING",
    "PYTHONUTF8",
    "HOME",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "HF_HOME",
    "TRANSFORMERS_CACHE",
)


def child_environment(spec: dict) -> dict:
    """
    The environment one server process is started
    with.

    A server is a subprocess of the host, so by
    default it would inherit everything the host
    holds - OPENAI_API_KEY included. A third-party
    HRIS connector has no need of our model key, and
    handing it over is how a tool integration turns
    into a credential leak. So the child gets an
    allow-list plus whatever its own config block
    declares, and nothing else.

    A server that genuinely needs a secret should be
    given that secret explicitly, in its own "env"
    block, where it is visible in the config diff.
    """

    environment = {
        name: os.environ[name]
        for name in PASSTHROUGH
        if name in os.environ
    }

    environment.update(spec.get("env", {}))

    return environment


@dataclass
class DiscoveredTool:

    server: str

    tool_name: str

    qualified_name: str

    description: str


@dataclass
class MCPToolset:
    """
    Servers, their sessions, and the tools they
    turned out to have.

    Kept alive by a background event loop, because
    the MCP client is async and the agent loop is
    not. The agent never sees this object - it gets
    `.as_toolset()`.
    """

    schemas: list = field(
        default_factory=list
    )

    tools: list = field(default_factory=list)

    calls: list = field(default_factory=list)

    _runner: object = None

    def tool_names(self) -> list:

        return [
            tool.qualified_name
            for tool in self.tools
        ]

    def by_server(self) -> dict:

        grouped = {}

        for tool in self.tools:

            grouped.setdefault(
                tool.server,
                [],
            ).append(tool.tool_name)

        return grouped

    def call(
        self,
        name: str,
        arguments: dict,
    ) -> dict:
        """
        Send one tools/call to whichever server owns
        the tool, and hand the result back as a dict.

        A server that answers with an error payload
        is not an exception here: a recoverable error
        is a result the model is meant to read and
        act on, so it goes back up the same path a
        success does.
        """

        self.calls.append(
            {
                "name": name,
                "arguments": arguments,
            }
        )

        return self._runner.call(
            name,
            arguments,
        )

    def as_toolset(self) -> Toolset:
        """
        The agent-facing view: exactly the Toolset
        `run_agent` already accepts.
        """

        return Toolset(
            name="mcp",
            schemas=self.schemas,
            functions={},
            sanitise=False,
        )

    def close(self):

        if self._runner is not None:
            self._runner.stop()


class _Runner:
    """
    One background thread running one asyncio loop,
    holding every server session open.

    MCP sessions are async context managers and the
    Week-7 agent loop is plain synchronous code. The
    honest options were to make the loop async - which
    would change the agent, the one thing this week
    must not do - or to keep the sessions on their own
    loop and talk to them across a thread boundary.
    This is the second.
    """

    def __init__(self):

        self.loop = asyncio.new_event_loop()

        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
        )

        self.thread.start()

        self.sessions = {}

        self.owner = {}

        self._stack = None

    def _run(self):

        asyncio.set_event_loop(self.loop)

        self.loop.run_forever()

    def submit(self, coro):

        return asyncio.run_coroutine_threadsafe(
            coro,
            self.loop,
        ).result(timeout=120)

    async def _open(self, servers: dict):

        from contextlib import AsyncExitStack

        from mcp import (
            ClientSession,
            StdioServerParameters,
        )
        from mcp.client.stdio import (
            stdio_client,
        )

        self._stack = AsyncExitStack()

        await self._stack.__aenter__()

        discovered = []

        for name, spec in servers.items():

            environment = child_environment(
                spec
            )

            parameters = StdioServerParameters(
                command=spec["command"].replace(
                    "${PYTHON}",
                    sys.executable,
                ),
                args=spec.get("args", []),
                env=environment,
                cwd=spec.get("cwd", BASE_DIR),
            )

            read, write = await (
                self._stack.enter_async_context(
                    stdio_client(parameters)
                )
            )

            session = await (
                self._stack.enter_async_context(
                    ClientSession(read, write)
                )
            )

            # The handshake. Everything the host
            # knows about this server comes from
            # these two calls - nothing is assumed.
            await session.initialize()

            listed = await session.list_tools()

            self.sessions[name] = session

            for tool in listed.tools:

                qualified = (
                    f"{name}__{tool.name}"
                )

                self.owner[qualified] = (
                    name,
                    tool.name,
                )

                discovered.append((name, tool))

        return discovered

    async def _call(
        self,
        name: str,
        arguments: dict,
    ):

        if name not in self.owner:

            return {
                "error": "unknown_tool",
                "message": (
                    f"No discovered tool named "
                    f"{name}."
                ),
            }

        server_name, tool_name = self.owner[
            name
        ]

        session = self.sessions[server_name]

        result = await session.call_tool(
            tool_name,
            arguments or {},
        )

        return unwrap(result)

    def call(
        self,
        name: str,
        arguments: dict,
    ) -> dict:

        return self.submit(
            self._call(name, arguments)
        )

    def open(self, servers: dict):

        return self.submit(
            self._open(servers)
        )

    def stop(self):

        async def shutdown():

            if self._stack is not None:
                await self._stack.aclose()

        try:
            self.submit(shutdown())

        except Exception:
            pass

        self.loop.call_soon_threadsafe(
            self.loop.stop
        )


def unwrap(result) -> dict:
    """
    An MCP tool result, as a plain dict.

    Servers here answer with a JSON string in a text
    block, which is the ordinary way to return
    structured data over MCP. If a server ever sends
    something else, the text is handed back as-is
    rather than being dropped.
    """

    # structured_content in mcp 2.x,
    # structuredContent in 1.x.
    structured = getattr(
        result,
        "structured_content",
        None,
    ) or getattr(
        result,
        "structuredContent",
        None,
    )

    if isinstance(structured, dict) and set(
        structured
    ) != {"result"}:
        return structured

    texts = []

    for block in getattr(
        result,
        "content",
        [],
    ) or []:

        text = getattr(block, "text", None)

        if text is not None:
            texts.append(text)

    joined = "\n".join(texts).strip()

    if not joined:
        return {
            "error": "empty_result",
            "message": (
                "The server returned no content."
            ),
        }

    try:
        parsed = json.loads(joined)

    except json.JSONDecodeError:
        return {"text": joined}

    if isinstance(parsed, dict):
        return parsed

    return {"result": parsed}


def discover_toolset(
    config_path: str = None,
) -> MCPToolset:
    """
    Start every configured server, ask each what it
    can do, and return the result as one toolset.

    This function does not know the name of a single
    tool. That is the test: adding a server to
    mcp_servers.json changes what the agent can do
    without changing a line of Python anywhere.
    """

    config = load_config(config_path)

    servers = enabled_servers(config)

    runner = _Runner()

    discovered = runner.open(servers)

    toolset = MCPToolset(_runner=runner)

    for server_name, tool in discovered:

        schema = to_openai_schema(
            tool,
            server_name,
        )

        toolset.schemas.append(schema)

        toolset.tools.append(
            DiscoveredTool(
                server=server_name,
                tool_name=tool.name,
                qualified_name=schema["name"],
                description=schema[
                    "description"
                ],
            )
        )

    return toolset
