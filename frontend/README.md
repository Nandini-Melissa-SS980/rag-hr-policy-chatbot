# HR360 Bot — frontend

React single-page app for the HR policy RAG backend in the parent directory.

## Run

Two terminals. The backend must be up first — the frontend proxies to it.

```bash
# terminal 1, from the repo root
uvicorn app.main:app --reload          # port 8000

# terminal 2, here
npm install
npm run dev                            # port 5173
```

Open <http://localhost:5173> — use `localhost`, not `127.0.0.1`: Vite binds
only localhost unless you pass `--host`.

`vite.config.ts` proxies `/api` to port 8000, so the backend needs no CORS
middleware and the app ships one base path. Set `VITE_API_BASE` only when the
backend lives on another origin.

## Commands

```bash
npm run dev         # dev server with HMR
npm test            # vitest, 27 tests
npm run lint        # oxlint
npm run typecheck   # tsc
npm run build       # production bundle to dist/
npm run preview     # serve the built bundle
```

## Layout

```
src/
  components/
    brand/Logo.tsx        the mark, inline SVG, full + glyph variants
    chat/                 MessageBubble, PromptComposer, QuickPrompts,
                          SourcesPanel
    layout/Sidebar.tsx
  pages/                  ChatPage, PoliciesPage
  services/api.ts         the one place that talks to FastAPI
  stores/conversations.ts history, in localStorage
  lib/policies.ts         the six real policies and the quick prompts
  types/api.ts            mirrors app/models/schemas.py
```

## Two things worth knowing

**History is browser-local.** `/api/chat` is stateless by design, so
conversations live in `localStorage` rather than being faked against an
endpoint that does not exist. Every read and write is guarded — storage throws
in private windows and returns nothing when site data is cleared, and the app
renders correctly in both cases.

**Retrieval-only mode exists for a reason.** Retrieval needs no model, so the
app stays fully demoable when the OpenAI key is unfunded. In that state
`/api/chat` returns a readable `429` and the UI explains it rather than showing
a stack trace.

## Types

`src/types/api.ts` mirrors `app/models/schemas.py`. Keep the two in step — a
field invented on this side renders as `undefined`, silently.
