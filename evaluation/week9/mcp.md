# MCP — Two Servers, One Unchanged Agent

Week 9 · M5. Discover tools over MCP instead of wiring them in, bolt on a
second server with config alone, and expose a server someone else's agent can
call.

```bash
python -m evaluation.week9.run_agent_mcp       # discovery + one real query
python -m evaluation.week9.capture_wire        # raw JSON-RPC -> wire.json
python -m evaluation.week9.error_transcript    # before/after error handling
python -m pytest tests/test_mcp.py
```

## Headline

| | |
| --- | --- |
| Tools discovered | **2 → 4** |
| Lines changed in `app/agent/` | **0** |
| Lines changed to add server two | **8**, all in `mcp_servers.json` |
| Tool from the new server, called in a trace | `hris__get_leave_balance` |
| Tests | 19 new, 119 total, all passing |

## Where the model runs

**In the host process, inside `run_agent`, and nowhere else.** The host calls
the model, the model picks a tool, and the host turns that choice into a
`tools/call` frame. Neither server holds an API key, imports a model client, or
is told which model — or whether any model — is calling. Pinned by
`test_no_server_can_reach_the_model`.

## 1. The three roles, as built

| Role | What it is here |
| --- | --- |
| **Host** | `app/agent/loop.py` — runs the model, owns the conversation. Unchanged since Week 8. |
| **Client** | `app/mcp/client.py` — starts servers, does the handshake, turns `tools/list` into schemas. |
| **Server** | `mcp_servers/policy_server.py`, `mcp_servers/hris_server.py` — two separate processes, stdio. |

## 2. Config-only swap

`git status` is the whole argument: every path is `??`, untracked and new. No
tracked file is modified, so `app/agent/` is byte-identical to the Week-8
commit — verified twice, by `diff -ru` against a snapshot taken before the HRIS
server was added, and by `git diff HEAD -- app/agent/` after it was called.
Full evidence in `agent_diff.txt`.

The entire change to gain two tools:

```diff
+    "hris": {
+      "command": "${PYTHON}",
+      "args": ["-m", "mcp_servers.hris_server"],
+      "enabled": true,
+      "env": {
+        "HRIS_SCOPES": "hris:leave,hris:grade"
+      }
     }
```

**Why it works.** Week 8 gave `run_agent` injectable `tool_schemas` and
`tool_call` so the trajectory eval could run two arms. The MCP client fills
those two arguments. The agent is never told where its tools come from, so a
new server cannot require an agent edit. `test_the_client_names_no_tool` and
`test_the_agent_does_not_import_mcp` keep it that way.

## 3. Tools before and after

Both counts come from `tools/list` at run time, not from a list in the code.

| Stage | Servers | Tools | Names |
| --- | --- | --- | --- |
| Before | policy | **2** | `policy__search_handbook`, `policy__get_policy_version` |
| After | policy, hris | **4** | + `hris__get_leave_balance`, `hris__get_grade_band` |

One query using both servers, from `agent_trace.json`:

```
[ 2] tool_call    hris__get_leave_balance({"employee_id": "HR-1002"})
[ 3] observation  {"employee_id": "HR-1002", "accrued_leave_days": 7.0, ...}
[ 5] tool_call    policy__search_handbook({"query": "annual leave entitlement full-time employees"})
[ 6] observation  {"passages": [{"policy_id": "HR-202", "section": "2.1", "score": 0.8699, ...
[ 8] answer       model returned a final answer
```

> The model here is a scripted stand-in — still no API credits (the 429 running
> since Week 4). It proves the plumbing: a tool discovered from the HRIS server
> is selected by name and invoked through the unchanged loop. `--live` runs the
> same path against the real model.

## 4. The wire

`wire.json` holds nine frames, intercepted between client and server rather
than transcribed, each top-level field annotated by hand.

```
1 client -> server  initialize          6 client -> server  tools/call
2 server -> client  initialize result   7 server -> client  tools/call result
3 client -> server  notifications/initialized   (no id — fire and forget)
4 client -> server  tools/list          8 client -> server  tools/call (failing)
5 server -> client  tools/list result   9 server -> client  recoverable error
```

Two things the capture shows that are easy to get wrong:

- **Frame 3 has no `id`.** It is a notification: no reply expected, and the
  server must not send one. Requests have ids so replies can be matched on a
  pipe where order is not guaranteed.
- **Frame 9 is `isError: false`.** An unknown employee is a *successful call*
  whose payload describes a business failure. That distinction is what lets the
  model read the problem and recover, instead of seeing a transport fault.

## 5. One tool rewritten

`get_policy_version` on my own server, same failing call both times. Full
transcripts in `error_before_after.md`.

| | Before | After |
| --- | --- | --- |
| Description | `Gets policy version.` | what it is for, *when to reach for it*, argument format with an example |
| Failure | `{"error": "Error 3"}` | names the cause, gives the earliest date that exists, `recoverable: true`, `retry_with` |
| Model recovered | **No** | **Yes** |
| Quoted a figure it could not support | **Yes** | **No** |

`Error 3` is indistinguishable from an outage, so the model could not tell *this
version does not exist* from *the server is down* — and, with no way to act,
answered anyway and quoted a current figure for a 2023 question. The described
failure produced a correct refusal plus a successful second call.

The docstring is not a comment. It ships over `tools/list` as the tool's
`description` and is the only thing the model reads when deciding whether to
call it, so it is written as a prompt.

## 6. Tools vs resources

The handbook **search** is a tool: the model decides when it needs a passage.
The handbook **itself** is not exposed as a tool, because it is context the app
should attach — making the model spend a turn fetching a document the host
could hand over for free. Noted in `policy_server.py`.

## 7. Least privilege — one real bug found

Writing `risk_note.md` caught a flaw in my own client: it passed the full
`os.environ` to every server, so the third-party HRIS connector received
`OPENAI_API_KEY`. Confirmed, then fixed — servers now get an allow-list plus
whatever their own config block declares. A server needing a secret must be
given it explicitly, where it shows up in the config diff.

Pinned by `test_the_model_key_is_not_handed_to_a_server`.

## 8. Bonus — scoped token

With `HRIS_SCOPES=hris:leave`, grade band is denied while leave balance keeps
working, and the denial reaches the model as something it can act on:

```json
{"error": "scope_denied", "missing_scope": "hris:grade",
 "recoverable": true, "retryable": false,
 "message": "... This will not succeed on retry. Answer from the policy
             handbook instead, and say that the HRIS field was not available."}
```

`retryable: false` matters: the model reports the gap instead of looping on it.

**Not built:** the single gateway process with one audit line per call. The
scoping and recoverable-denial half is done and tested; the fan-out front door
is not, and is the obvious next piece.

## 9. Caveats

- **The model is a stand-in** in both the agent run and the error transcript —
  no API credits. Every MCP mechanism is real; model *judgement* is not tested.
- **The HRIS server is local**, written to behave like an outside system (own
  id format, own error vocabulary, own token check). A real third party would
  also bring latency, downtime and version skew.
- **`risk_note.md` answers "what does it log?" with "unknown"**, which is the
  honest answer for a binary nobody here has read, and the reason the note
  recommends shipping leave-only.

## Files

| File | Role |
| --- | --- |
| `../../mcp_servers.json` | The config — the only thing edited to add a server |
| `../../app/mcp/client.py` | Discovery, dispatch, environment scrubbing |
| `../../mcp_servers/policy_server.py` | Server one, and the rewritten tool |
| `../../mcp_servers/hris_server.py` | Server two, with scopes |
| `agent_diff.txt` | The zero-line proof |
| `config_diff.txt` | The eight lines that added server two |
| `wire.json` | Nine annotated JSON-RPC frames |
| `tool_counts.md` | 2 → 4, from `tools/list` |
| `error_before_after.md` | The rewritten tool, both ways |
| `risk_note.md` | Five-line supply-chain note |
| `../../tests/test_mcp.py` | 19 tests |
