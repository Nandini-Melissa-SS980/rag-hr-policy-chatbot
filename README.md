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
documents/addenda/       Source PDFs
vectorstore/             Chroma index (generated)
scripts/ingest.py        Build the index
evaluation/              Golden set, results, report
```
