# Error Analysis — 20 Traces, Open Coded and Ranked

Week 5 · M3. Read a fair sample of real traces, write one honest note per
failure, group the notes into named problems, rank them, and pick the
next fix.

```bash
python -m evaluation.trace_capture   # writes traces.jsonl
```

## What is captured in a trace

One complete request, replayable: the question, the chunks that were
fetched (full text, not previews), the scores, whether the app abstained,
the answer, the cited sources, and the config that produced it
(`strategy`, `top_k`, embedding model, generator model, `rerank`).

`traces.jsonl` — one JSON object per line, 20 traces.

## How the sample was drawn

`question_pool.json` holds **45 questions** written the way an employee
would actually ask, *before* anything was run — so the pool could not be
shaped by knowing which questions the app handles well. It deliberately
includes vague one-word queries (`"leave?"`, `"wfh"`) and questions about
HR topics the six indexed policies do not cover.

`trace_capture.py` then draws **20 of the 45 at random with a fixed seed**
(`random.Random(42).sample`). Reproducible, and not curated: the sample
picked whatever it picked, including five questions that turned out to be
the most damaging.

## Limitation: generation could not be observed ⚠️

A complete trace needs the answer. `OPENAI_API_KEY` is configured but the
account returns `429 insufficient_quota`, and no local model is installed,
so **0 of 20 traces carry an answer**. `traces.jsonl` records the
`generation_error` per trace and keeps the retrieval half intact.

Everything below is therefore coded on **what was retrieved and whether
the app chose to answer** — both of which happen before the model is
called. Generation-side problems (hallucination, miscitation, incomplete
answers, ignoring the context) **are not represented in this taxonomy at
all**, and would very likely add groups once a generator is available.
Re-run `trace_capture.py` after unblocking one to fill them in.

---

## 1. Open-coded notes — one per trace

Written by reading each trace in order, before any grouping. Codes were
assigned afterwards.

| Trace | Question | Honest note | Code |
| --- | --- | --- | --- |
| T01 | How many days of annual leave do I get? | Rank 1 is the bare heading `2 Annual Leave` (14 chars, no information). The chunk that actually answers — §2.1, twenty-five days — is at rank 3. | empty-chunk |
| T02 | How many days a week can I work from home? | Correct chunk (HR-207 §4.2) is rank 1. Rank 2 is HR-201 §2.1 standard working hours, unrelated. | ok, minor noise |
| T03 | Which days do I have to come into the office? | Ranks 1–2 are the attendance policy. The answer — Tuesday and Wednesday anchor days, HR-207 §4.2 — is at rank 3, one slot from being cut. | wrong-policy-first |
| T04 | Can I work from another country for a few weeks? | Rank 1 does contain the answer ("remote work must be performed from the employee's country of employment") but it sits in a chunk labelled `section=unknown`, so it cannot be cited properly. | unciteable |
| T05 | Can I work fully remote? | HR-207 §4.2 at rank 1, which covers fully remote by exception. Clean. | ok |
| T06 | Can I carry unused leave into next year? | HR-202 §2.5 correct at rank 1. Rank 2 is the empty `2 Annual Leave` heading. | ok, wasted slot |
| T07 | Can I use my own laptop for work? | Answer is at rank 2 (§5, company data only on company-provided devices). Reasonable. | ok |
| T08 | How am I rated in my review? | HR-203 §5.1 and §5.2 at ranks 1–2, both correct. Best trace in the batch. | ok |
| T09 | When does the leave year start? | HR-202 §2.3 correct at rank 1. Rank 2 is the empty heading again. | ok, wasted slot |
| T10 | Do I get a pay rise with a promotion? | HR-205 §3.4 correct at rank 1. Rank 2 is the empty `3 Promotion` heading. | ok, wasted slot |
| T11 | What if my promotion is turned down? | Rank 1 is the empty `3 Promotion` heading. The real answer (unsuccessful nominees get written feedback) lives in a `section=unknown` chunk and was not retrieved at all. | empty-chunk + missing |
| T12 | How much maternity leave do I get? | **Nothing in the corpus covers maternity leave.** The app retrieved annual leave sections at 0.70 and chose to answer. It will almost certainly report the twenty-five-day annual entitlement as maternity leave. | out-of-scope |
| T13 | What is the pension contribution? | No pension policy exists. Retrieved annual leave chunks at 0.63 and chose to answer. | out-of-scope |
| T14 | Do we get private health insurance? | No such policy. Retrieved annual leave and remote-working eligibility at 0.54 and chose to answer. | out-of-scope |
| T15 | How do I claim travel expenses? | No travel policy. Retrieved HR-207 §4.3 *Equipment and Expenses* at 0.67 — which is about home-office allowance. The most dangerous case in the batch: the chunk is topically adjacent, so any answer will read as authoritative and be wrong. | out-of-scope |
| T16 | Is there a training budget? | No training policy. Retrieved the equipment/expenses section and an empty heading, and chose to answer. | out-of-scope |
| T17 | leave? | Two of the three slots are empty headings (`2 Annual Leave`, `4 Making a Request`). Only one slot carries content. A one-word query gets a two-thirds-empty context. | empty-chunk |
| T18 | How do I book time off? | Retrieved HR-201 working hours and rest breaks. The correct section — HR-202 §2.4 *Requesting and Taking Annual Leave* — is **absent from the top 3 entirely**. A very common question answered from the wrong policy. | wrong-policy-first |
| T19 | What are my working hours? | Rank 1 is the empty `2 Working Hours` heading; the answer §2.1 is at rank 2. | empty-chunk |
| T20 | How long is my lunch break? | Rank 1 is §2.2 *Rest Breaks* (twenty minutes), but lunch is defined in §2.1 (one hour, unpaid) at rank 2. The wrong one of two similar sections is first, inviting a "twenty minutes" answer. | near-miss |

---

## 2. Named problem groups

Five groups, named so a stranger can tell what each one is.

### A. Empty heading chunks take the best slots

Structure-aware chunking emits a chunk for a section heading whose body is
entirely sub-sections, so chunks like `2 Annual Leave` (14 chars) and
`3 Promotion` (11 chars) enter the index carrying no information.

**Seven** such heading chunks are in the index — HR-201/2, HR-201/3,
HR-202/2, HR-203/5, HR-204/4, HR-205/3, HR-207/4 — of which five appear
in this sample. An eighth chunk under 60 characters, HR-201/`unknown`
(`"the first day back at work."`), is a page-boundary fragment rather than
a heading; it belongs to group D but merges the same way.

They embed close to *any* question about their topic, so they win top
slots and displace the section that holds the answer.

**14 of 20 traces** have one in the top 3. **8 of 20** have one at
**rank 1**. With `top_k=3`, one of three context slots is wasted; T17
wastes two.

### B. Out-of-scope questions are answered instead of refused

Five sampled questions are about HR topics with no policy in the corpus —
maternity leave, pension, health insurance, travel expenses, training
budget. The abstention gate (`has_good_match`, threshold `0.45`) fired on
**none of them**.

**This cannot be fixed by raising the threshold.** The scores overlap:

```
out-of-scope top-1 scores : 0.539  0.621  0.627  0.672  0.703
in-scope     top-1 scores : 0.664  0.665  0.697  0.704  0.711  ...  0.839
```

Maternity leave (0.703) scores *higher* than "How do I book time off?"
(0.664). Any threshold that rejects the out-of-scope questions also
rejects legitimate ones. Across all 20 traces the lowest top-1 score is
**0.539** against a threshold of **0.45**, so the gate is effectively dead
code — it cannot fire on this corpus.

### C. Right topic, wrong policy retrieved

The question matches a policy's *vocabulary* rather than its subject.
T18 "How do I book time off?" pulls HR-201 *Working Hours* and *Rest
Breaks* instead of HR-202 §2.4 *Requesting and Taking Annual Leave*.
T03 pushes the correct remote-working section to rank 3 behind two
attendance chunks. **2 of 20**, and one of them is a question employees
would ask constantly.

### D. Correct content in an unciteable chunk

Page-boundary text becomes its own chunk with `section=unknown`. T04's
answer is in one. **4 of 20** traces retrieve such a chunk. The content
is right, but the citation the app is built to produce —
`policy_id` + `section` — is unusable, which matters more here than in a
general chatbot because citation *is* the product.

### E. Near-miss between two similar sections

Two sections of one policy cover adjacent facts and the wrong one ranks
first. T20 puts *Rest Breaks* (twenty minutes) above the section that
defines the one-hour lunch break. **1 of 20**, plus T11 as a variant.
Low frequency, but it produces a confidently wrong number.

---

## 3. Ranking — frequency × severity

Severity is judged by what a wrong answer costs an employee relying on it.

| Rank | Group | Frequency | Severity | Why that severity |
| --- | --- | --- | --- | --- |
| **1** | **B. Out-of-scope answered** | 5/20 (25%) | **Critical** | States a policy that does not exist. An employee could act on invented maternity or pension terms. Worst possible failure for a compliance tool. |
| **2** | **A. Empty heading chunks** | **14/20 (70%)** | Medium | Rarely wrong on its own, but silently costs a third of the context on most requests, and it is the mechanism behind several near-misses. |
| **3** | C. Wrong policy retrieved | 2/20 (10%) | High | The answer is not in the context at all, so the model can only guess or refuse. |
| **4** | D. Unciteable chunk | 4/20 (20%) | Medium | Answer correct, citation broken. Undermines trust rather than the fact. |
| **5** | E. Near-miss sections | 1/20 (5%) | Medium | Wrong specific number, stated confidently. |

B outranks A despite being a third as frequent: 70% of requests wasting a
slot is a tax, while 25% of requests inventing HR policy is a hazard.

---

## 4. Chosen fix target

**Group A — merge empty heading chunks into the section that follows.**

Not group B, even though B ranks first. B's analysis shows a threshold
change *cannot* work, because out-of-scope and in-scope scores overlap.
Fixing B properly needs a new mechanism — a relevance check on the
retrieved chunks, or a coverage guard listing which topics the corpus
covers — which is a larger piece of work and a new failure surface. It is
the right *second* target, and it is now understood well enough to plan.

A is chosen because it is the highest-frequency group, the fix is confined
to one function in `chunker.py`, the mechanism is fully understood, and
the effect is directly measurable with the Week 4 harness.

### Prediction, written before making the change

Merge any chunk under 60 characters into the chunk that follows it, so
`2 Annual Leave` becomes the opening line of `2.1 Entitlement`.

1. `structure_aware` chunk count drops from **65 to 57** (eight chunks
   under 60 characters absorbed into the chunk that follows them).
2. **hit-rate@1 rises**, because 8 of 20 traces currently waste rank 1 on
   an empty chunk. Baseline is 0.500; I expect **0.58–0.67**.
3. **hit-rate@3 rises slightly at best.** Freeing a slot helps only where
   the correct chunk sat at rank 4 — Q11 is the one known candidate.
   Baseline 0.875; I expect **0.875–0.917** (0 or 1 question gained).
4. **MRR rises** by roughly the same shape as hit@1, from 0.667 to
   **0.70–0.78**.
5. **Section labels change for the merged chunks**, so `questions.json`
   ground truth must be re-checked before trusting any delta.
6. It will **not** fix groups B, C or D. T18 will still retrieve the wrong
   policy; the out-of-scope five will still be answered.

If hit@1 does not move, my model of this failure is wrong — it would mean
the empty chunks were being retrieved but not actually displacing the
correct section, and I should re-read the traces before changing anything
else.

---

## Files

| File | Role |
| --- | --- |
| `question_pool.json` | 45 realistic questions, written before any run |
| `trace_capture.py` | draws the seeded sample, captures traces |
| `traces.jsonl` | the 20 traces this analysis was coded from |
| `error_analysis.md` | this document |
