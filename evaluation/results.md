# Retrieval Evaluation

> **Status: not yet run.** `documents/base_handbook/` and `documents/addenda/` are
> empty, so there is no index to evaluate. Every number below is a target or a
> worked example, not a measurement. `retrieval_results.json` is a placeholder
> that records the report schema.
>
> To produce real results:
>
> ```bash
> # 1. add the PDFs
> #    documents/base_handbook/employee_handbook.pdf
> #    documents/addenda/HR-201.pdf … HR-207.pdf
> uvicorn app.main:app --reload
> curl -X POST http://127.0.0.1:8000/ingest
>
> # 2. score each golden question against retrieval only
> curl -X POST http://127.0.0.1:8000/retrieve \
>   -H 'content-type: application/json' \
>   -d '{"question": "How many weeks of paid parental leave am I entitled to?"}'
> ```
>
> `/retrieve` returns the ranked chunks with `vector_score`, `keyword_score`,
> `superseded`, and `superseded_by` — everything the metrics below need. Run it for
> each entry in `questions.json`, compare `doc_id`s against `expected_docs`, and
> record the run in `retrieval_results.json` using the schema in that file.

## What is being measured

Retrieval is scored on its own, before generation. If the right passage is not in
the context window, no amount of prompt tuning fixes the answer — so the golden
set asserts on **which documents come back**, not on answer wording.

| Metric | Definition | Target |
| --- | --- | --- |
| `hit_rate_at_k` | Share of in-scope questions with at least one expected document in the top *k* | ≥ 0.95 |
| `recall_at_k` | Mean fraction of a question's expected documents retrieved | ≥ 0.90 |
| `mrr` | Mean reciprocal rank of the first expected document | ≥ 0.80 |
| `precedence_accuracy` | Share of precedence cases where every retrieved *withdrawn* passage was flagged `superseded` | 1.00 |

`precedence_accuracy` is the one that has to be perfect. A miss there means the
chatbot can state a withdrawn entitlement as current policy — the failure mode
that actually costs the business something.

## Golden set

14 questions in `questions.json`, grouped by what they stress:

| Category | Count | What it probes |
| --- | --- | --- |
| `entitlement` | 4 | Numeric answers (weeks, days, amounts) that must be quoted exactly |
| `eligibility` | 2 | Service-length and status conditions |
| `process` | 3 | Notice periods, approvals, deadlines |
| `lookup` | 1 | Exact identifier ("what does HR-204 say") — the case dense retrieval blurs |
| `precedence` | 2 | Addendum-overrides-handbook and addendum-overrides-addendum |
| `out_of_scope` | 2 | Nothing covers it; the system must decline instead of inventing |

Several questions are worded the way an employee would ask, deliberately sharing
no vocabulary with the policy heading ("Am I allowed to work from home full
time?" against a section titled *Remote and Hybrid Working*). Paraphrase
robustness is the point.

### Assumed corpus

`expected_docs` in `questions.json` assumes these topics. **Reconcile them with
your actual PDFs before trusting any score** — a wrong expectation reads as a
retrieval failure.

| Document | Assumed topic | Precedence |
| --- | --- | --- |
| `employee_handbook.pdf` | Base handbook, numbered sections (4.1 annual leave, 4.2 parental leave, …) | Overridden by any addendum |
| `HR-201.pdf` | Bereavement leave | **Superseded by HR-205** |
| `HR-202.pdf` | Remote and hybrid working, home-office stipend | Current |
| `HR-203.pdf` | Parental leave | **Supersedes handbook §4.2** |
| `HR-204.pdf` | Expenses and business travel | Current |
| `HR-205.pdf` | Bereavement leave update | **Supersedes HR-201** |
| `HR-207.pdf` | Performance review cycle | Current |

`HR-206` is absent from the corpus. That is per the supplied file list, not an
oversight — but if it exists in your source set, add it and extend the golden set,
since a missing addendum is exactly the kind of gap that produces a confidently
wrong answer about superseded policy.

## How precedence is scored

The retriever reads override declarations out of the addenda themselves at
ingest time (`supersedes Section 4.2`, `supersedes HR-201`), stores them as chunk
metadata, and applies them at query time:

1. Any retrieved addendum contributes its superseded sections and documents.
2. A retrieved passage matching one of those is flagged `superseded=true`,
   annotated with the addendum that replaced it, and multiplied by
   `SUPERSEDED_PENALTY` (0.45) so current policy outranks it.
3. Section matching is hierarchical: replacing `4.2` also replaces `4.2.1`, but
   not `4.20`.

Withdrawn passages are demoted, **not dropped**. "What changed about bereavement
leave?" (Q07) needs the old text — it just has to arrive labelled. The system
prompt then instructs the model to treat `SUPERSEDED` excerpts as historical and
name the replacing addendum.

A precedence case counts as passing only when *every* retrieved withdrawn
document was flagged. Not retrieving it at all is not scored as a precedence
failure — it shows up as a recall failure instead.

## Reading a failure

`retrieval_results.json` keeps per-chunk `vector_score` and `keyword_score`
alongside the final score, which usually localises the problem without a
debugger:

| Symptom | Likely cause | First thing to try |
| --- | --- | --- |
| Right document, wrong page/section | Chunks too large — one passage spans two policies | Lower `CHUNK_SIZE_TOKENS` (350 → 250) |
| `keyword_score` high, `vector_score` low, expected doc missing | Paraphrase gap the embedding model can't bridge | Raise `KEYWORD_WEIGHT`, or move to a stronger embedding model |
| Identifier lookups (Q10) fail | Lexical signal underweighted | Raise `KEYWORD_WEIGHT` (0.25 → 0.4) |
| Expected doc present but ranked last | Candidate pool too shallow before re-ranking | Raise `CANDIDATE_K` |
| `precedence_ok` false | The override sentence didn't match the loader's regex | Check `supersedes_sections` in the chunk metadata; the wording in the PDF may differ |
| Answer correct but `grounded: false` | Model answered without emitting citation markers | Check the excerpt headers reached the prompt intact |
| Out-of-scope question returns a confident answer | `MIN_SCORE` is 0.0, so weak matches still reach the model | Raise `MIN_SCORE` until Q13/Q14 return nothing |

## Tuning order

Retrieval parameters interact, so change one at a time and re-score. Scoring via
`/retrieve` never calls the model, so a full sweep of the golden set costs
nothing but the local embedding pass.

1. **Chunk size / overlap** — the largest single effect. Section-boundary splits
   already prevent two policies sharing a chunk; size controls how much
   surrounding context each answer gets.
2. **`keyword_weight`** — trades paraphrase robustness against exact-identifier
   precision. 0.25 is a starting point, not a finding.
3. **`candidate_k`** — cheap. Raise it before touching anything else if an
   expected document is retrieved but ranked low.
4. **`min_score`** — the abstention threshold. Tune it against the out-of-scope
   questions specifically; raising it to fix a false positive will start costing
   recall elsewhere.
5. **Embedding model** — last, because it invalidates the whole index. Re-ingest
   is required.

## Known limitations

- **Scanned PDFs yield nothing.** `pypdf` extracts text, not images. A scanned
  handbook needs OCR upstream; the loader logs a warning and produces zero pages,
  and `/ingest` returns 422 rather than silently indexing an empty corpus.
- **Override detection is regex-based.** It handles "supersedes Section 4.2" and
  "replaces HR-201". An addendum that conveys the same thing in prose ("the
  parental leave provisions of the handbook no longer apply") will not be
  detected, and the stale passage will not be flagged. Verify
  `supersedes_sections` metadata after ingesting a new addendum.
- **Effective dates are parsed, not compared.** Precedence comes from explicit
  supersession statements, not from date ordering. Two undeclared conflicting
  addenda would both be presented as current — the prompt instructs the model to
  surface the conflict rather than pick one.
- **No answer-quality scoring yet.** Only retrieval is measured. Faithfulness
  scoring (does every claim in the answer trace to a cited excerpt?) would need a
  second pass, most usefully as an LLM-judge over the `answer_must_contain` fields
  already present in `questions.json`.
- **Scoring is manual.** There is no runner script in this project — `/retrieve`
  is the interface, and aggregating the metrics across the golden set is left to
  whatever you drive it from.
- **The tests' fake embedder is lexical, not semantic.** Unit tests verify ranking
  mechanics and precedence logic; they do not tell you whether the real embedding
  model retrieves well. That is what this evaluation is for.
