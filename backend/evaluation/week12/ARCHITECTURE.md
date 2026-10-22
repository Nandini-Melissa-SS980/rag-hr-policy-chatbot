# Architecture — Policy Answer Desk

One page. Boxes, arrows, where the model calls happen, where
the money goes.

---

## The request path

```
  employee question + employee_id
              |
              v
  +-------------------------------------------+
  |  app/desk/answer.py                        |   SINGLE ENTRY POINT
  |  answer_policy_question()                  |   python -m app.desk
  +-------------------------------------------+
              |
   (1) RESOLVE  ---------------------------------> employee record
              |                                    data/employees.json
              |                                    or HRIS over MCP
              |   entity: IN | UK      <- record, never the question
              |   grade:  1-7          <- record, never the question
              |   as_of:  a date       <- the question, or today
              |
   (2) GUARD  ----------------------------------->  refuse, no retrieval
              |   about a colleague?               app/desk/answer.py
              |   uncovered subject?               app/desk/scope.py
              |
   (3) RETRIEVE ----------------------------------> Chroma
              |                                    hr_policy_desk
              |   where entity IN (mine, GLOBAL)    28 chunks
              |   top_k * 3  (over-fetch)
              |        |
              |   filter_in_force(as_of)    <- drops superseded editions
              |   annex_wins(entity)        <- annex outranks handbook
              |   [:top_k]
              |
   (4) DECIDE -----------------------------------> handoff to HRBP
              |   top score < 0.45  -> refuse      app/desk/answer.py
              |   discretionary     -> handoff
              |
   (5) ANSWER
              |   generator present -> ONE model call   <-- the only
              |   generator absent  -> quote the clause      model call
              |
   (6) CITE    policy_id + section + VERSION + EFFECTIVE DATE + entity
              |
              v
      answer to employee        redacted answer to log
                                     |
                                     v
                        logs/*.jsonl  one trace id, spans per stage
                                     |
                                     +--> LangSmith (optional)
```

---

## Where the model calls happen

**Exactly one, at step 5.** Everything before it is
deterministic: a dictionary lookup, two regexes, a vector
search and three filters.

That is deliberate. Resolution, scoping and version
filtering decide whether the answer is *about the right
person under the right law*, and none of those should depend
on a model's judgement. The model's job is to phrase what the
filters already selected.

With no funded key the desk returns the cited clause verbatim
instead. Less fluent, equally correct, and the whole system
stays demonstrable.

---

## Where the money goes

| stage | cost | latency | why |
|---|---|---|---|
| resolve | $0 | 0.09 ms | dict lookup |
| guard | $0 | <1 ms | regex |
| retrieve | **$0** | **341 ms** | local embedding model |
| decide | $0 | <1 ms | comparisons |
| answer | **$0.000286** | ~1 s live | the one model call |

**100% of spend is generation; 100% of latency is retrieval.**
They are different bottlenecks and scale differently — which
is why the 10x answer is about retrieval throughput and the
cost answer is about input tokens.

Full numbers in COST.md.

---

## What the pieces are, and which week they came from

| component | file | week |
|---|---|---|
| chunking + index | `services/chunker.py`, `markdown_loader.py` | 3, 12 |
| retrieval | `desk/retriever.py` over Chroma | 4, 12 |
| eval harness, judge | `evaluation/week12/run_integrated.py` | 6, 12 |
| agent loop + budgets | `agent/loop.py` | 7 |
| trajectory eval | `evaluation/trajectory_eval.py` | 8 |
| MCP servers + client | `mcp_servers/`, `app/mcp/client.py` | 9 |
| orchestrator (raced, killed) | `agent/orchestrator.py` | 10 |
| tracing, spans, cost | `app/observability.py` | 11 |
| desk: resolve/scope/redact | `app/desk/` | 12 |

Week 10's orchestrator is in the repo and **not** in the
request path. It lost its own race — same quality, 10% more
cost, 1.5x the model calls — and shipping it anyway would
contradict the evidence.

---

## MCP, both directions

**Consumed:** `app/mcp/client.py` starts each server in
`mcp_servers.json`, performs the handshake, asks `tools/list`,
and hands the result to the agent loop as schemas plus a
dispatcher. Adding a server is a config edit.

**Exposed:** `mcp_servers/policy_server.py` offers
`search_handbook` and `get_policy_version` over stdio;
`mcp_servers/hris_server.py` offers `get_leave_balance` and
`get_grade_band`, scoped by `HRIS_SCOPES` so a client can be
granted one and not the other.

No MCP server holds an API key or can reach a model. Servers
start with a scrubbed environment so a third-party connector
never sees `OPENAI_API_KEY`.

---

## The three filters, in order, and why order matters

1. **entity** — in the Chroma query. A chunk from the other
   entity's annex is never returned, so it cannot rank and
   cannot be cited.
2. **edition** — after retrieval, because Chroma cannot
   express the date window. Over-fetch compensates; see
   SEAMS.md S1 for the bug this caused.
3. **precedence** — a reorder, not a filter. The annex rises
   above the handbook; the handbook stays available so an
   answer can still say what the general case is.

Resolution precedes all three. Retrieving before resolving is
how a correctly cited clause becomes a different employee's
answer.
