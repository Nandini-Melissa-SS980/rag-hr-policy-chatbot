# HR Policy RAG Chatbot

Retrieval-augmented Q&A over HR policy PDFs. Answers come only from the
retrieved policy text and carry citations.

- API: FastAPI
- Answers: OpenAI (`gpt-5-mini`)
- Embeddings: `BAAI/bge-small-en-v1.5` (local, via sentence-transformers)
- Vector store: Chroma, persisted to `vectorstore/`

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Set `OPENAI_API_KEY` in `.env`. The app will not start without it.

Policy PDFs go in `documents/addenda/`.

## Ingest

```bash
python -m scripts.ingest
```

Loads the PDFs and builds two collections, one per chunking strategy:
`hr_policy_basic` and `hr_policy_structure_aware`. Re-run after changing the
PDFs or the chunker.

## Run

```bash
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

## Layout

```
app/
  main.py                FastAPI app
  config.py              Environment settings
  api/chat.py            Routes
  models/schemas.py      Request/response models
  services/
    document_loader.py   PDF text extraction
    chunker.py           Both chunking strategies + metadata
    embeddings.py        Local embedding model
    vector_store.py      Chroma wrapper
    retriever.py         Search by strategy
    generator.py         Prompt + OpenAI call
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
  week10/                The multi-agent race, its log and its verdict
  week9/                 MCP evidence: wire.json, diffs, risk note
  trajectory_eval.py     Expected tool sequences, both arms, the four numbers
  injection_probe.py     Indirect injection, attacked and defended
  frozen_index.py        The policy index read without the embedding model
```
