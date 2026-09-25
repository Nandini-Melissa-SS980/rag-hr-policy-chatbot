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
  agent/
    loop.py              The agent loop and its budgets
    tools.py             The three tools, and build_toolset()
    workflow.py          The same task as fixed steps
    guardrails.py        Free-text sanitiser, output guardrail
documents/addenda/       Source PDFs
vectorstore/             Chroma index (generated)
scripts/ingest.py        Build the index
evaluation/              Golden sets, harnesses, reports
  trajectory_eval.py     Expected tool sequences, both arms, the four numbers
  injection_probe.py     Indirect injection, attacked and defended
  frozen_index.py        The policy index read without the embedding model
```
