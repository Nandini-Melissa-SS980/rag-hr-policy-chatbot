# 10-minute demo — Policy Answer Desk

Four parts, to the clock. Every command below runs from
`backend/` and has been run as written.

A flawless demo is a red flag. Part 2 is the longest part on
purpose.

---

## Setup (before the clock starts)

```bash
cd backend
..\.venv\Scripts\activate
python -m scripts.ingest_desk     # 28 chunks, ~20s
```

---

## Part 1 — a real run (2:30)

**The point: grade and entity are resolved from the record
BEFORE retrieval, and the citation names the version.**

```bash
python -m app.desk --demo --today 2025-06-01
```

Four questions. Talk over them:

**Q1 and Q2 are the same question.** "How much paid parental
leave do I get as the primary carer?" — asked by E-1003 and
E-1001.

| | E-1003 | E-1001 |
|---|---|---|
| resolved | IN, grade 3 | UK, grade 6 |
| answer | **26 weeks** | **39 weeks**, enhanced to 26 at full pay |
| cited | HR-A-IN §A3.1 v2025.1 eff 2025-01-01 | HR-A-UK §A3.1 v2025.1 eff 2025-01-01 |

Different entity, different grade, different annex, different
figure. Neither fact is in any document — both come from the
record, and the line `-> entity IN, grade 3` on screen is the
tool call that read it.

**Q3 is the version case.** "What was I entitled to for
parental leave in March 2024?" resolves `as_of 2024-03-01`
and every citation comes back `v2024.1`. The 2024 edition is
still in the index — employees legitimately ask about last
year, and deleting it would delete the test, not the bug.

**Q4 is the handoff.** "Can I extend my parental leave by a
month?" returns `[handoff]`, citing HR-A-IN §A5, which says
extensions are decided by an HR business partner. It does not
guess.

> If asked "show me it refusing a colleague question":
> ```bash
> python -m app.desk --employee E-1003 "How much leave does E-1001 get?"
> ```
> Refuses without confirming E-1001 exists, their grade, or
> their entity. The shape of the refusal leaks as surely as
> its content.

---

## Part 2 — the failures I found (3:30)

**The point: these were found by reading traces, and three of
them were created by integration.**

Open `evaluation/week12/SEAMS.md`.

### The one integration created: S2, the discretionary hijack

Both entity annexes end with "discretionary matters". That
clause is retrieved for nearly any question about that annex
and lands 0.03–0.08 below the top match whatever was asked.

- **First rule** — presence anywhere is decisive — sent
  **8 of 32** eval cases to a human, including "how much
  parental leave do I get".
- **Second rule** — a similarity margin — sent the same 8.
  The margin needed to catch a real extension request (0.015)
  is smaller than the noise between clauses in one short
  document.
- **Third rule, which holds** — rank, *or* the question
  itself asking for a departure.

Neither part was wrong alone. Retrieval was fine. The clause
was fine. Composition broke it.

### The one with a frequency: S3, out-of-scope answered

**4 of 4** `out_of_scope` cases failed before the fix. A
pension question scored **0.614** against an annual-leave
clause — above the 0.45 gate — so the desk answered it, with
a correct citation to the wrong subject.

The measurement that kills the obvious fix:

| | top score range |
|---|---|
| in-scope questions | 0.718 – 0.885 |
| out-of-scope questions | 0.552 – 0.773 |

Overlapping. "What is my salary band" scores **0.773**,
higher than "what notice do I give" at 0.718. **No threshold
separates them**, which is why the fix is a subject gate and
why that gate is Weakness 1.

### The one the panel will ask about: the PII line

Show the raw log line, not the policy:

```bash
python -c "import json;from app.observability import read_traces;print(json.dumps([x for x in read_traces('logs/week12_eval.jsonl') if x['labels'].get('eval_case')=='C01'][0],indent=2)[:900])"
```

Question, answer, citation with version and effective date,
context ids. **No grade, no band, no tenure, no leave
balance.** `employee_id` IS there — the support drill needs
it to find a complaint.

Then say how it was found: **by auditing the raw log, not by
reading the redaction policy.** The first audit found **272
violations across 192 traces** — the extractive answer ended
"...which applies to you as grades 1-4 in the IN entity", and
the answer is logged.

### The two other weaknesses, written down Wednesday

`evaluation/week12/WEAKNESSES.md`, unprompted:

1. **The scope gate is a hand-maintained deny list.** A
   seventh uncovered subject answers from the nearest leave
   clause at ~0.6 with a confident citation.
2. **Retrieval ranks the wrong clause of the right
   document.** "What was I entitled to in March 2024" cites
   §3.3 Notice above §3.1 Entitlement. The citation is
   honest and the answer is about the wrong thing. **The
   eval suite does not catch this** — `check_clause` asserts
   the clause appears somewhere, not that it ranks first.

---

## Part 3 — a number that moved (2:00)

```bash
python -m evaluation.week12.run_integrated
```

**Out-of-scope answer rate, before → after the subject gate:**

| | before | after |
|---|---|---|
| out_of_scope cases passing | **0 / 4** | **4 / 4** |
| whole suite | 26 / 32 (81%) | **32 / 32 (100%)** |
| cases pinning BOTH grade and entity | 10 / 14 (71%) | **14 / 14 (100%)** |

n = 32 cases across 7 modes.
Judge agreement with the deterministic assertions: **100%**
(n=20; 12 cases not judged because only answered cases are
judged for grounding).

**Prove the suite can fail.** Break the entity filter and
re-run:

```
entity filter pinned to UK for everyone
TOTAL  32  22  69%
cases pinning BOTH grade and entity: 8/14 (57%)
```

100% is only meaningful because 69% is reachable.

### What the suite does not measure at all

**Whether the policies are legally correct.** They are
authored fixtures. The suite checks the system quotes the
right clause for the right person under the right edition. It
checks nothing about whether that clause is right.

Also not covered: paraphrase, multi-turn, load, and
adversarial prompting beyond the third-party probe.

---

## Part 4 — what's next (2:00)

### The closed loop, live

The PII leak is now a test. Show it fails without the fix:

```bash
# remove the one call
python -m pytest tests/test_desk.py -k "protected_values" -q
#   1 failed    <- RED

# restore it
python -m pytest tests/test_desk.py -k "protected_values" -q
#   1 passed    <- GREEN
```

202 tests pass overall.

### Cost per question

**$0.000179** per question — estimated, and say so. The
measured number is **$0.000000** because the OpenAI key
returns 429, so the desk answered extractively.

The estimate is the real payload at the real list price:
505 input + 80 output tokens, 62.5% of questions answered
(the rest refuse before the model is reached).

**100% of spend is generation; 100% of latency is
retrieval** (341 ms, local embedding model).

### At 10x, what breaks first

**Nothing.** 700 questions/month → 7,000 is a peak minute of
**2.0 requests**. One worker serves **176/min** on retrieval
latency. **89x headroom**, and $1.25/month.

Claiming "cost breaks first" would be inventing a constraint.
The number that transfers: **single-worker retrieval
throughput binds at ~89x**, around 62,000 questions/month,
and the fix is a second process because the desk is
stateless.

### Ranked next, costed

1. **Cross-encoder rerank** — fixes Weakness 2. Already in
   this repo from Week 4, not wired into the desk. ~80 ms,
   $0.
2. **Entailment check** — replaces the deny list with
   something that generalises. One extra model call, roughly
   doubles cost per query to ~$0.00036.
3. **HRBP hand labels on 50 answers** — the only item that
   makes the judge number mean anything outside this repo.
   A half-day of someone who is liable for the policy set.

---

## Hostile questions — the short answers

**"How many eval cases pin BOTH grade and entity, and what do
those score?"**
14 of 32. **14/14, 100%.** Before the fixes, 10/14.

**"Which policy version does your retriever return on
2 January? Is effective date a filter your code enforces?"**
Enforced, in two places. Entity is a Chroma `where` clause so
the other annex is never returned. The edition window is
`filter_in_force()` after retrieval, because Chroma cannot
express the date range — and that split caused S1, where
superseded near-duplicates ate the retrieval window.

**"Show me one raw log line. Who can read that log?"**
Command in Part 2. Everyone with the repo — which is why
grade, band, tenure and leave balance are not in it, and why
there is an `audit()` function and a test.

**"If it gives the wrong maternity entitlement and someone
plans four months around it, who is on the hook?"**
The refusal path is `app/desk/answer.py` steps 2, 2b, 4 and
5, and the assertion that enforces it is `check_status` over
11 cases expecting `refused` or `handoff`. The system prefers
a handoff to a guess on anything the policy marks
discretionary. It does not remove liability from HR; it
removes the category of answer where nobody can say which
clause it came from.

**"Your judge agreed with your labels. Why take that into a
grievance meeting?"**
You should not, and Weakness 3 says so in writing. 100%
agreement is agreement with *my own rules* against a corpus
*I wrote*. It measures faithful reporting, not legal
correctness. For a grievance meeting you need the policy set
signed off by someone liable for it — then this suite tells
you the system is quoting that set correctly.
