"""
The raw JSON-RPC, captured off the wire.

    python -m evaluation.week9.capture_wire

Runs a real session against the HRIS server and
writes every frame that crossed the pipe to
wire.json, in order, with a hand-written annotation
on each top-level field.

Nothing here is transcribed by hand. The frames are
intercepted between the MCP client and the server's
stdin/stdout, so what lands in wire.json is what the
two processes actually said to each other. The
annotations are mine; the bytes are theirs.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

from app.config import BASE_DIR


WIRE_PATH = os.path.join(
    BASE_DIR,
    "evaluation",
    "week9",
    "wire.json",
)


# Hand-written, one per top-level field of each
# frame. Keyed by (method-or-kind, field).
ANNOTATIONS = {
    "initialize.request": {
        "jsonrpc": (
            "Always the string 2.0. MCP is "
            "JSON-RPC 2.0 and nothing else - this "
            "field is what makes the frame legal "
            "JSON-RPC rather than an ad-hoc blob."
        ),
        "id": (
            "Request id, chosen by the client. The "
            "server must echo it back so the "
            "client can match a reply to a request "
            "on a pipe where replies may arrive "
            "out of order. Notifications have no "
            "id, which is exactly what makes them "
            "notifications."
        ),
        "method": (
            "The RPC being invoked. 'initialize' "
            "is the first call of every MCP "
            "session and may not be preceded by "
            "anything else."
        ),
        "params": (
            "Arguments to the method. For "
            "initialize: the protocol version the "
            "client speaks, the capabilities it "
            "offers, and who it says it is. No "
            "model, no prompt, no API key - the "
            "server is never told which AI is "
            "calling, or whether there is one."
        ),
    },
    "initialize.response": {
        "jsonrpc": "2.0, as above.",
        "id": (
            "Echoes the request id, so this is the "
            "answer to that initialize and not to "
            "something else."
        ),
        "result": (
            "The server's half of the handshake: "
            "the protocol version it agrees to, "
            "the capabilities it actually has "
            "(here 'tools'; a server with nothing "
            "to list would say so), its name and "
            "version, and optional instructions. "
            "This is negotiation, not "
            "configuration - the client adapts to "
            "what comes back."
        ),
    },
    "notifications/initialized": {
        "jsonrpc": "2.0, as above.",
        "method": (
            "'notifications/initialized'. The "
            "client confirming the handshake is "
            "complete and it is ready for normal "
            "traffic."
        ),
        "_no_params": (
            "The client sent no 'params' at all "
            "here. Nothing needs saying; the "
            "message itself is the signal."
        ),
        "_no_id": (
            "There is deliberately no 'id' field. "
            "This is a notification: fire and "
            "forget, no reply expected, and the "
            "server must not send one."
        ),
    },
    "tools/list.request": {
        "jsonrpc": "2.0, as above.",
        "id": "New request id for this call.",
        "method": (
            "'tools/list'. Discovery. The client "
            "is asking what this server can do "
            "rather than being told in advance - "
            "this single call is why adding a "
            "server needs no agent code."
        ),
        "params": (
            "Empty here. It can carry a cursor "
            "when a server has more tools than fit "
            "in one page."
        ),
    },
    "tools/list.response": {
        "jsonrpc": "2.0, as above.",
        "id": "Echoes the tools/list request id.",
        "result": (
            "The catalogue: a 'tools' array, each "
            "entry with a name, a description and "
            "an input_schema (JSON Schema). The "
            "description is the tool's docstring, "
            "and it is the prompt the model will "
            "read when it decides whether to call "
            "this tool - which is why the "
            "docstrings on these servers are "
            "written for a reader, not a compiler. "
            "The host turns each entry into a "
            "function schema for the model."
        ),
    },
    "tools/call.request": {
        "jsonrpc": "2.0, as above.",
        "id": "New request id for this call.",
        "method": (
            "'tools/call'. Invocation. This is the "
            "only frame in the session caused by a "
            "model decision - the model, running "
            "in the host, chose this tool, and the "
            "host turned that choice into this "
            "frame."
        ),
        "params": (
            "'name' is the tool as listed (server "
            "prefixes are the host's own "
            "bookkeeping and are stripped before "
            "sending), and 'arguments' is an "
            "object that must satisfy that tool's "
            "input_schema. The arguments were "
            "produced by the model; the server "
            "validates them regardless, because a "
            "server cannot trust its caller."
        ),
    },
    "tools/call.response": {
        "jsonrpc": "2.0, as above.",
        "id": "Echoes the tools/call request id.",
        "result": (
            "'content' is a list of blocks - here "
            "one text block holding a JSON string, "
            "the ordinary way to return structured "
            "data. 'isError' false means the CALL "
            "succeeded at the protocol level; a "
            "business failure such as an unknown "
            "employee still arrives as a "
            "successful call whose payload "
            "describes the problem, which is what "
            "lets the model read it and recover "
            "instead of seeing a transport fault."
        ),
    },
}


class Tap:
    """
    Sits between the client and the pipe, copying
    every frame as it passes.
    """

    def __init__(self):
        self.frames = []

    def record(
        self,
        direction: str,
        payload: dict,
    ):

        self.frames.append(
            {
                "seq": len(self.frames) + 1,
                "direction": direction,
                "at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "frame": payload,
            }
        )


def classify(frame: dict) -> str:
    """
    Which annotation block describes this frame.
    """

    method = frame.get("method")

    if method == "notifications/initialized":
        return "notifications/initialized"

    if method:
        return f"{method}.request"

    return None


async def capture():

    from contextlib import AsyncExitStack

    from mcp import (
        ClientSession,
        StdioServerParameters,
    )
    from mcp.client.stdio import stdio_client

    tap = Tap()

    parameters = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "mcp_servers.hris_server",
        ],
        env=dict(os.environ),
        cwd=BASE_DIR,
    )

    pending = {}

    async with AsyncExitStack() as stack:

        read, write = await (
            stack.enter_async_context(
                stdio_client(parameters)
            )
        )

        # Wrap the two streams so every message is
        # copied on its way past. The session below
        # is a completely ordinary MCP client; it
        # does not know it is being watched.
        original_send = write.send

        async def watched_send(message):

            payload = json.loads(
                message.message.model_dump_json(
                    by_alias=True,
                    exclude_none=True,
                )
            )

            kind = classify(payload)

            if payload.get("id") is not None and (
                payload.get("method")
            ):
                pending[payload["id"]] = payload[
                    "method"
                ]

            tap.record(
                "client -> server",
                payload,
            )

            return await original_send(message)

        write.send = watched_send

        original_receive = read.receive

        async def watched_receive():

            message = await original_receive()

            payload = json.loads(
                message.message.model_dump_json(
                    by_alias=True,
                    exclude_none=True,
                )
            )

            tap.record(
                "server -> client",
                payload,
            )

            return message

        read.receive = watched_receive

        session = await (
            stack.enter_async_context(
                ClientSession(read, write)
            )
        )

        await session.initialize()

        await session.list_tools()

        # One successful call, and one that fails in
        # a way the model is meant to recover from.
        await session.call_tool(
            "get_leave_balance",
            {"employee_id": "HR-1002"},
        )

        await session.call_tool(
            "get_leave_balance",
            {"employee_id": "E-1002"},
        )

    return tap.frames, pending


def annotate(
    frames: list,
    pending: dict,
) -> list:

    annotated = []

    for entry in frames:

        frame = entry["frame"]

        method = frame.get("method")

        if method == "notifications/initialized":
            key = "notifications/initialized"

        elif method:
            key = f"{method}.request"

        else:
            origin = pending.get(frame.get("id"))

            key = (
                f"{origin}.response"
                if origin
                else None
            )

        notes = ANNOTATIONS.get(key, {})

        annotated.append(
            {
                **entry,
                "what_this_is": key,
                "field_notes": {
                    field: notes[field]
                    for field in notes
                },
            }
        )

    return annotated


def main():

    frames, pending = asyncio.run(capture())

    annotated = annotate(frames, pending)

    document = {
        "captured_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "server": "hris (server two)",
        "transport": (
            "stdio - newline-delimited JSON-RPC "
            "2.0 over the child process's stdin "
            "and stdout"
        ),
        "where_the_model_runs": (
            "In the host process, and only there. "
            "The host calls the model, the model "
            "chooses a tool, and the host turns "
            "that choice into the tools/call frame "
            "below; the server holds no API key, "
            "imports no model client, and is never "
            "told which model - or whether any "
            "model - is calling it."
        ),
        "frame_count": len(annotated),
        "frames": annotated,
    }

    with open(
        WIRE_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(document, file, indent=2)

    for entry in annotated:

        frame = entry["frame"]

        print(
            f"{entry['seq']:>2} "
            f"{entry['direction']:<17} "
            f"{entry['what_this_is'] or '?'}"
        )

    print(f"\nWrote {WIRE_PATH}")


if __name__ == "__main__":
    main()
