# Policy Answer Desk

Answers an HR policy question **for a specific employee**: resolves their
grade and entity from the employee record first, retrieves only the policy
edition that was in force, lets the entity annex override the handbook, cites
the clause with its version and effective date, and hands discretionary
matters to an HR business partner rather than guessing.

```bash
cd backend
python -m scripts.ingest_desk          # build the index, ~20s
python -m app.desk --demo --today 2025-06-01
```

That is the whole system end to end. The same question asked by two employees
returns two different answers from two different annexes, each cited with its
version and effective date.

| | |
|---|---|
| Entry point | `python -m app.desk` |
| Eval suite | `python -m evaluation.week12.run_integrated` -> 32/32, judge agreement 100% |
| Tests | `python -m pytest tests -m "not slow"` -> 202 passing |
| Capstone docs | [`backend/evaluation/week12/`](backend/evaluation/week12/) |

**Start here:** [DEMO.md](backend/evaluation/week12/DEMO.md) &middot;
[ARCHITECTURE.md](backend/evaluation/week12/ARCHITECTURE.md) &middot;
[SEAMS.md](backend/evaluation/week12/SEAMS.md) &middot;
[WEAKNESSES.md](backend/evaluation/week12/WEAKNESSES.md) &middot;
[COST.md](backend/evaluation/week12/COST.md)

Built over twelve weeks; the sections below are the parts it is made of.

---

## The stack

- API: FastAPI
- Answers: OpenAI (`gpt-5-mini`)
- Embeddings: `BAAI/bge-small-en-v1.5` (local, via sentence-transformers)
- Vector store: Chroma, persisted to `backend/vectorstore/`

## Model provider

The generator and the judge run on OpenAI by default. To use
**Gemini Flash** instead, which has a free tier of roughly 1,500
requests/day and needs no card:

1. Get a key at <https://aistudio.google.com/apikey> (starts `AIza`)
2. Add to `backend/.env`:

```bash
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIza...
```

3. Restart whatever is running. No code change.

Both providers go through `app/services/llm.py`, which hides the
difference: Gemini speaks `chat.completions` where OpenAI speaks
`responses`, takes the system prompt as a message rather than an
`instructions=` argument, reports `prompt_tokens` rather than
`input_tokens`, and wraps JSON in a ```` ```json ```` fence that has
to be stripped before parsing.

**The Week-7 agent loop stays on OpenAI either way.** It does tool
calling, the two providers disagree on the shape of a tool call, and
the Week-8 trajectory eval and Week-10 race both read OpenAI's
`function_call` items — switching it would invalidate numbers already
reported. The loop is replayed in every eval, so it never needs a live
model. A test pins this.

A missing `GEMINI_API_KEY` under `LLM_PROVIDER=gemini` raises rather
than falling back to OpenAI: a trace that names the wrong model is
worse than an error.

## Repo layout

```
backend/     FastAPI app, the agent, the eval harnesses, the policy PDFs
frontend/    HR360 Bot - React + TypeScript single-page app
.venv/       one virtualenv, at the root, shared by everything in backend/
```

**Every Python command below is run from `backend/`.** The paths in the
harnesses are relative to it, and `BASE_DIR` is derived from the package
location, so running them from the repo root will not find the index.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
```

Set `OPENAI_API_KEY` in `backend/.env`. The app will not start without it.

Policy PDFs go in `backend/documents/addenda/`.

## Ingest

```bash
cd backend
python -m scripts.ingest
```

Loads the PDFs and builds two collections, one per chunking strategy:
`hr_policy_basic` and `hr_policy_structure_aware`. Re-run after changing the
PDFs or the chunker.

## Frontend (HR360 Bot)

A React + TypeScript single-page app in `frontend/`, talking to the FastAPI
backend. Two terminals:

```bash
cd backend && uvicorn app.main:app --reload    # terminal 1, port 8000
cd frontend && npm install && npm run dev      # terminal 2, port 5173
```

Open http://localhost:5173. Vite proxies `/api` to port 8000, so the backend
needs no CORS middleware and the app ships one base path.

| | |
| --- | --- |
| Stack | React 19, TypeScript, Vite, Tailwind v4, TanStack Query, React Router |
| Pages | Chat, and Policies (what the corpus actually covers) |
| History | `localStorage` — the backend is stateless by design |
| Tests | `npx vitest run` — 17 passing |

Two things the UI does that a generic chat skin would not:

**Sources under every answer.** Cited `HR-202 §2.1` chips, expandable to the
retrieved passages with their scores. Heading-only chunks are labelled as such,
because the index contains a few (`"2 Working Hours"`, 15 characters, no body)
that can never answer anything.

**A retrieval-only toggle.** Retrieval needs no model, so the app stays fully
demoable while the OpenAI key is unfunded. `/api/chat` now returns a readable
`429` in that case rather than an opaque `500`, which is what lets the UI
explain the failure instead of showing a stack trace.

The quick-prompt chips are real questions this corpus answers (annual leave,
working hours, remote work, flexible working, performance reviews). They
retrieve at ~0.8; a vague query like "hey" scores 0.57 and returns the
heading-only chunks, which is worth seeing once.

## Run the API alone

```bash
cd backend
uvicorn app.main:app --reload
```

Docs at http://127.0.0.1:8000/docs

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Liveness |
| GET | `/api/stats` | Indexed chunk count |
| POST | `/api/search` | Retrieval only, with scores |
| POST | `/api/chat` | Answer with citations |

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "content-type: application/json" \
  -d '{"question": "How many days can I work from home?"}'
```

Body accepts an optional `region` to filter by metadata. If the top retrieval
score is below 0.45, `/api/chat` refuses instead of answering.

## Evaluation

```bash
python -m evaluation.evaluate_retrieval
```

Scores both chunking strategies against `evaluation/questions.json` and writes
`evaluation/retrieval_results.json`.

## Trajectory evaluation

```bash
python -m evaluation.trajectory_eval          # both arms, no API needed
python -m evaluation.trajectory_eval --live   # same scoring, real model
python -m evaluation.injection_probe          # indirect injection, attack and defence
```

Scores the path the agent took rather than only its final answer: tool-choice
accuracy, argument validity, step efficiency, and cost per question at p50 and
max, for ten cases with their expected tool sequences asserted in code. Runs a
baseline arm and a one-change arm in the same process and reports the
outcome-vs-trajectory gap, the per-mode counts before and after, and what the
change cost. Writes `evaluation/trajectory_results.json`; the write-up is
`evaluation/trajectory.md`.

Set `INPUT_COST_PER_1M` and `OUTPUT_COST_PER_1M` in `.env` or the cost columns
are zero. With no funded key the trajectories are replayed from authored plans
rather than captured from the API - `evaluation/trajectory.md` section 0 says
exactly which parts of the numbers that affects.

`injection_probe.py` plants an instruction in an employee record's free-text
manager comment, shows it reaching the model, then turns on the three defences
in `app/agent/guardrails.py` and re-attacks. The poisoned comment is written in
at run time and restored afterwards, so the committed fixture stays clean.

## MCP servers

```bash
python -m evaluation.week9.run_agent_mcp     # discover tools, run one query
python -m evaluation.week9.capture_wire      # raw JSON-RPC -> week9/wire.json
python -m evaluation.week9.error_transcript  # recoverable-error before/after
```

The agent discovers its tools over MCP rather than having them wired in.
`mcp_servers.json` lists the servers; `app/mcp/client.py` starts each one,
performs the handshake, asks `tools/list`, and hands the result to the
unchanged agent loop as schemas plus a dispatcher.

Adding a server is a config edit and nothing else - no Python changes, which
`evaluation/week9/agent_diff.txt` proves for the HRIS server. Two servers ship
here: `mcp_servers/policy_server.py` (handbook search) and
`mcp_servers/hris_server.py` (grade band and leave balance, scoped by
`HRIS_SCOPES`).

The model runs in the host, inside `run_agent`. No MCP server holds an API key
or can reach a model, and servers are started with a scrubbed environment so a
third-party connector never sees `OPENAI_API_KEY`. The write-up is
`evaluation/week9/mcp.md`.

## Multi-agent race

```bash
python -m evaluation.week10.race_multi          # replayed model
python -m evaluation.week10.race_multi --live   # real model + Week-6 judge
```

A manager plus two specialists - a policy retrieval worker and an eligibility
calculation worker - raced against the single agent on the same ten Week-6
cases, with the same judge and the same pass rule. Each specialist holds a
subset of the tools; handing either one the full set would delete the only
plausible source of a win.

**The squad lost.** Over the nine cases where nothing was broken both arms
score 7/9, and the squad costs 10% more per question while making 1.5x the
sequential model calls. The verdict is `evaluation/week10/verdict.md`.

Two things the numbers only show if you print both views. The squad sends
*fewer* input tokens than the single agent, because a narrow worker carries a
narrow tool schema (139 tokens against 444) - so the raw re-send multiplier
comes out at 0.8x, below 1.0, and that is not a win. And a worker that fails
early is cheap, so the injected 500 on E13 drags the squad's ten-case cost
average down into a false tie. Both the ten-case and the clean-nine numbers
are reported for that reason.

Outputs, all generated:

```
evaluation/week10/
  race_table.md       four metrics x two arms, the ten cases named
  handoffs.log        every hand-off with its own token count
  failure_case.md     the injected 500, and what the manager actually did
  verdict.md          keep/kill, with the sunk cost named
  race_results.json   every row behind the tables
```

## LangSmith

The JSONL log is the source of truth. LangSmith is the dashboard on top — a
run tree per request, retrieval inspection, token and cost columns, and
datasets built from real traffic.

```bash
cd backend

# key from https://smith.langchain.com, into backend/.env
# LANGSMITH_API_KEY=ls__...

# backfill the traces already on disk
python -m evaluation.week11.to_langsmith

# and/or send new ones as they happen
LANGSMITH_ENABLED=1 uvicorn app.main:app --reload
```

Off unless `LANGSMITH_ENABLED=1`. The exporter swallows its own failures and
the JSONL row is written first, so a dashboard being down can never cost a
request or a log line — there is a test for each of those.

Each request becomes one run tree:

| our stage | LangSmith run type | what the UI shows |
| --- | --- | --- |
| the request | `chain` | question, answer, prompt version, cost |
| `retrieval` | `retriever` | each chunk with its text, score and section |
| `generation` | `llm` | prompt/completion token counts |

**LangSmith, yes. LangChain, not in the request path.** The usual route is
`@traceable` or LangChain's auto-instrumentation, both of which assume
LangChain owns retrieval and generation. Here it does not: the retriever, the
generator and the agent loop are hand built, and rewriting them as LCEL chains
would delete the structures the Week-7, 8 and 10 evals measure — the budget
termination log, the hand-off token accounting, the trajectory eval. So
`app/langsmith_export.py` posts run trees directly with the `langsmith`
client, which needs no LangChain. The dashboard is the same; the
instrumentation stays explicit.

## Observability and the support drill

```bash
python -m evaluation.week11.seed_logs                      # a week of traffic + one bad answer
python -m evaluation.week11.logcli --answer "notice"       # the slice that found it
python -m evaluation.week11.run_suite --prompt-version v1  # RED
python -m evaluation.week11.run_suite --prompt-version v2  # GREEN
python -m evaluation.week11.cost_report                    # cost by stage, and 10x
```

Every request writes one row to `logs/requests.jsonl` with per-stage latency,
tokens and cost, the prompt version, and the retrieved context ids.
`app/observability.py` holds the recorder; `app/services/answering.py` is the
one instrumented path the API and the drill both use, so a trace captured in
the drill has the same shape as a production trace.

**The drill.** Complaint: *"it quoted the wrong notice period, maybe Tuesday."*
Found in **00:41** from 197 requests, on the **output** slice — 1 hit, against
9 for the input slice and 29 for Tuesday. The trace showed `prompt_version: v1`
and five retrieved passages, none about notice periods: this corpus has no
notice policy, everything scored ~0.7, `has_good_match` waved it through, and
the model answered a resignation question out of the annual-leave section.
Write-up in `evaluation/week11/drill.md`.

**The fix** is a prompt bump, v1 → v2, adding one on-topic rule. Suite went
18/30 → 22/30 with the three new cases 0/3 → 3/3 and `BROKEN: []`. The full
suite is what caught the first attempt overshooting into E21, a real question
the corpus does answer. Canary and rollback in `evaluation/week11/rollback.md`.

Prompts are versioned in `app/services/prompts.py` and old versions are never
deleted — a trace from last Tuesday has to keep resolving to the text that ran.

```
evaluation/week11/
  drill.md              mm:ss, the slice, the missing-field analysis
  trace.json            the found request, per-span
  regression_cases.json E28/E29/E30, added to the Week-6 suite
  suite_red.txt         18/30, drill 0/3
  suite_green.txt       22/30, drill 3/3
  to_langsmith.py       backfill the log into LangSmith
  cost_by_stage.md      retrieval / generation / tools
  tenx.md               what binds first, with the number
  rollback.md           prompt version bump, canary, rollback
```

## Layout

```
backend/
  app/
    main.py                FastAPI app
    config.py              Environment settings
    observability.py       Traces, spans, per-stage cost
    langsmith_export.py    The same traces, as LangSmith run trees
    api/chat.py            Routes
    models/schemas.py      Request/response models
    services/
      document_loader.py   PDF text extraction
      chunker.py           Both chunking strategies + metadata
      embeddings.py        Local embedding model
      vector_store.py      Chroma wrapper
      retriever.py         Search by strategy
      generator.py         Prompt + OpenAI call
      prompts.py           Versioned prompts, v1 and v2
      answering.py         The one instrumented answer path
    mcp/
      client.py            Tool discovery over MCP, and dispatch
    agent/
      loop.py              The agent loop and its budgets
      tools.py             The three tools, and build_toolset()
      workflow.py          The same task as fixed steps
      guardrails.py        Free-text sanitiser, output guardrail
      orchestrator.py      Manager + two specialists, with hand-off accounting
  documents/addenda/       Source PDFs
  vectorstore/             Chroma index (generated)
  scripts/ingest.py        Build the index
  mcp_servers.json         Which MCP servers to discover tools from
  mcp_servers/             MCP servers this repo exposes
    policy_server.py       Handbook search, over stdio
    hris_server.py         Grade band and leave balance, scoped
  evaluation/              Golden sets, harnesses, reports
    week11/                The support drill, the failure->test loop, cost
    week10/                The multi-agent race, its log and its verdict
    week9/                 MCP evidence: wire.json, diffs, risk note
    trajectory_eval.py     Expected tool sequences, both arms, the four numbers
    injection_probe.py     Indirect injection, attacked and defended
    frozen_index.py        The policy index read without the embedding model

frontend/                HR360 Bot - React single-page app
  src/components/        brand, chat, layout
  src/pages/             ChatPage, PoliciesPage
  src/services/api.ts    the one place that talks to FastAPI
  src/stores/            conversation history, localStorage

.venv/                   shared virtualenv, at the repo root
```
