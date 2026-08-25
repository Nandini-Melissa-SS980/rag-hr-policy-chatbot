# Retrieval Evaluation — Failure Separation, One Change, Measured

Week 4 · M2. Separate retrieval failures from generation failures, make
**exactly one** change, and report the before-and-after number.

Run with:

```bash
python -m evaluation.evaluate_retrieval   # writes retrieval_results.json
python -m evaluation.inspect_run          # writes inspection.md
python -m evaluation.inspect_run --answers  # adds generated answers (needs a funded API key)
```

## The harness, frozen before anything was changed

| Setting | Value |
| --- | --- |
| Embedding model | `BAAI/bge-small-en-v1.5` (384-d, local, cosine) |
| Candidate pool | 10 |
| Scored at | **k = 3** |
| Golden set | 24 questions, `questions.json` |
| Hit criterion | retrieved chunk matches expected `(policy_id, section)` |
| Authoritative arm | `structure_aware` (65 chunks) |

Baseline and change are measured **in one run of one harness**
(`ARMS` in `evaluate_retrieval.py`), so the ruler cannot drift between
the before and the after.

### Two harness corrections made before measuring

These are fixes to the *instrument*, not improvements to the app. Neither
is "the one change".

1. **Scored at k=3, not k=5.** The previous script retrieved and scored
   at `top_k=5`. It now retrieves 10 and scores at 3, which also records
   the rank a missed chunk *did* reach — the number that separates a
   reranking problem from a retrieval problem.
2. **The golden set was too easy to measure anything.** On the original
   8 questions the authoritative arm scored **hit@3 = 1.00**. A saturated
   metric cannot be improved, only damaged, so 16 harder questions were
   added *before* any baseline was accepted as final. They were designed
   from the documents — families of near-identical sections, identifier
   lookups, and zero-overlap paraphrases — not from any observed failure
   of the change.

### The `basic` arm is not measurable, and that is a labelling bug

`basic` scores **hit@3 = 0.29** — but that number is close to
meaningless. `extract_section` takes the first number in a blind
1000-character window, so a chunk opening `HR-201 Attendance…` is
labelled section `201`. `basic` contains no chunk labelled `2.1`, `3.1`,
`2.4`, or `5.1`, which several questions expect, so those questions
cannot hit regardless of retrieval quality.

Pinned by `test_extract_section_picks_up_the_policy_number`. Not fixed —
fixing it is a different change, and this week allows one.

## 1. Failure labelling, with evidence

Baseline (`structure_aware`, k=3): **21 / 24 hits**. Three misses, all of
them **retrieval failures**. Evidence from `inspection.md`:

| Q | Question | Expected | Retrieved at ranks 1–3 | Kind |
| --- | --- | --- | --- | --- |
| Q11 | How long are flexible working requests kept on file? | HR-204 / 6 | HR-204/3, HR-204/4.2, HR-204/4 | retrieval — right policy, wrong section |
| Q12 | How long are promotion nominations kept on file? | HR-205 / 5 | HR-205/3.2, HR-205/3.1, HR-205/unknown | retrieval — right policy, wrong section |
| Q22 | I need a temporary change to my hours for a couple of weeks | HR-204 / 4.1 | HR-201/2, HR-201/2.1, HR-204/2 | retrieval — wrong policy entirely |

The diagnosis is specific: **two of the three are "right document, wrong
section"**. Q11 and Q12 ask about record retention; each policy has a
short `Records` section whose wording is nearly identical across HR-203,
HR-204 and HR-205, and it is dominated by the longer, topic-heavy
sections of the same policy. Q22 fails differently — "temporary change to
my hours" pulls HR-201 *Working Hours* instead of HR-204 §4.1 *Informal
Arrangements*.

### Generation failures could not be observed

Bucket 2 — "right document, wrong answer" — requires running the
generator. `OPENAI_API_KEY` is configured but the account returns
`429 insufficient_quota`, so no answers could be produced. This is a
billing limit, not a code path: `inspect_run.py --answers` produces the
side-by-side view the moment the key is funded.

What can be stated without the LLM: for all 21 questions that hit at k=3,
the expected chunk **was** in the context window, so any wrong answer on
those would necessarily be a generation failure, not a retrieval one.

### A third bucket, checked and empty

`has_good_match` refuses to answer when the top score is below `0.45`. A
correct chunk retrieved just under that threshold would look like a
retrieval failure but is really a threshold problem.

Measured: the **lowest** top-1 score across all 24 questions is **0.586**,
against a threshold of 0.45. The gate never fires on this set, so there
are zero abstention failures. Worth knowing the bucket is empty rather
than assuming it.

## 2. The one change: cross-encoder reranking

Chosen from the Phase-1 data, not from preference. Every baseline miss had
its expected chunk **inside the candidate pool but below rank 3** — that
is the precise condition reranking addresses, and the condition under
which hybrid keyword search adds nothing, since the chunk is already
being fetched.

`app/services/reranker.py` — `BAAI/bge-reranker-base`, loaded once via
`lru_cache`, mirroring `embeddings.py`. The bi-encoder scores question and
chunk separately and never compares them; the cross-encoder reads the pair
together. Retrieval widens to `top_k × 3` candidates and the cross-encoder
reorders them.

Gated behind `Retriever(strategy, rerank=False)`, imported lazily, so the
baseline path is byte-identical and both arms run from one codebase. No
new dependency — `CrossEncoder` ships inside `sentence-transformers`.

The original cosine score is preserved as `vector_score`, because
`has_good_match` thresholds on the cosine scale and rerank scores are
unbounded logits.

## 3. Before and after

| Metric | Baseline | + Reranking | Δ |
| --- | --- | --- | --- |
| **hit-rate@3** | **0.875** (21/24) | **0.875** (21/24) | **0.000** |
| hit-rate@1 | 0.500 (12/24) | **0.625** (15/24) | **+0.125** |
| hit-rate@5 | 0.875 | **0.958** | +0.083 |
| MRR | 0.667 | **0.774** | +0.107 |

**The headline result is a null.** hit-rate@3 did not move.

That flat number hides real movement in both directions — two fixed, two
broken, cancelling exactly:

| Outcome | Questions | Rank before → after |
| --- | --- | --- |
| **fixed** | Q12, Q22 | miss → 1, miss → 2 |
| **newly broken** | Q2, Q16 | 2 → 5, 2 → 8 |
| improved but already passing | Q4, Q7, Q10, Q13, Q21 | e.g. Q13 3 → 1 |
| degraded but still passing | Q6, Q18 | 1 → 2 |
| unchanged | 13 questions | — |

So reranking is genuinely good at *ordering* — it recovered two of the
three baseline misses and lifted hit@1 by 12.5 points and MRR by 0.107 —
but at k=3 its gains and losses offset. **Had only hit-rate@3 been
recorded, this change would have looked like it did nothing at all.**

## 4. What the change did not fix

**Q11 — still broken.** Reranking moved HR-204/6 from outside the pool to
**rank 4**: better, still one place short of k=3. The `Records` sections
are two lines long and share almost all their wording across three
policies. Reranking cannot fix that; it is a chunk-granularity problem,
and the likely real fix is merging very short sections into their parent
or attaching the policy title to each chunk.

**Q16 — newly broken, 2 → 8.** *"Do I get paid extra for staying late?"*
expects HR-201/2.3 (*Overtime*). The reranker put HR-202/2.1 and HR-202/2.4
on top — annual leave sections, which do contain the word *paid*. The
correct chunk never says "paid extra": the answer is a **negation**
(overtime is compensated as time off in lieu, not money). A cross-encoder
rewards lexical-semantic agreement with the question, so a chunk whose
answer contradicts the question's framing gets pushed down. This is a real
weakness of reranking, not a labelling artifact.

**Q2 — newly broken, 2 → 5, but the ground truth is arguable.** *"What is
the company's policy on employee attendance and working hours?"* expects
HR-201/3.1. The reranker returned HR-201/1 (*Purpose and Scope*) and the
policy header. For a question that broad, those are defensible answers and
the reranker is arguably more right than the label. The label was **not**
changed after seeing this result — retro-fitting ground truth to flatter a
change is how an evaluation stops meaning anything. It is recorded as a
caveat instead.

**The `basic` arm's section labels** are still wrong, and `region` /
`effective_date` are still `"unknown"` on every chunk, so region filtering
still returns nothing (pinned by `test_unknown_region_returns_nothing`).
Both are out of scope for a one-change week.

## 5. Considered and rejected

| Alternative | Why not, on this evidence |
| --- | --- |
| **Hybrid BM25 + RRF** | The strongest remaining candidate. Rejected *first* because every baseline miss was already inside the candidate pool — the failure was ordering, not recall, and hybrid's advantage is recall. Worth revisiting for Q11/Q12: both name their policy in the question ("flexible working", "promotion"), which exact-term matching would weight heavily and reranking evidently does not. |
| **Query rewriting / HyDE** | Aimed at vocabulary mismatch. The `no_overlap` questions (Q17, Q19, Q20) already hit at rank 1, so paraphrase is not this system's bottleneck. |
| **MMR** | Fixes redundancy in the top-k. Inspection shows the top 3 are distinct sections, not near-duplicates, so there is no redundancy to remove. |
| **A stronger LLM** | Cannot help. All three failures happen before the model is called — the correct chunk is not in the context window. |

## 6. Measurement caveats

- **24 questions**, so hit-rate@3 moves in steps of 0.042. A one-question
  change is a 4.2-point swing.
- The golden set is **self-authored**, from the same six PDFs it scores.
  It is adversarial by construction but not independent.
- `recall_at_k` equals `hit_rate_at_k` throughout, because every question
  has exactly one expected target. Both are reported because they diverge
  as soon as a question has more than one, and `expected` already accepts
  a list.
- Reranking costs a second model pass over 30 candidates per query — the
  latency is not measured here.

## Files

| File | Role |
| --- | --- |
| `questions.json` | 24-question golden set, tagged by category |
| `metrics.py` | hit-rate@k, recall@k, MRR |
| `evaluate_retrieval.py` | frozen harness; all three arms; before/after comparison |
| `inspect_run.py` | writes `inspection.md` |
| `inspection.md` | the side-by-side view failures were labelled from |
| `retrieval_results.json` | full measured run, per-question ranks |
| `../app/services/reranker.py` | the one change |
