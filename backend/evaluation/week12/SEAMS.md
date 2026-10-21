# Seam list

What broke at the joins when eleven weeks of parts were wired
into one system. Unedited — including the ones I did not fix.

Each seam is a defect that existed in neither part alone.

---

## S1 — Superseded editions ate the retrieval window

**fixed**

The entity filter runs inside the Chroma query; the edition
window runs after, in Python, because Chroma cannot express
"effective_date <= X and (superseded_on empty or > X)".

With both the 2024 and 2025 leave policies indexed, the same
clause appears twice at nearly the same score — §3.3 scored
0.743 in both editions. A `top_k` of 6 was therefore consumed
by three clauses in two editions each, and anything ranked
below them never survived the date filter.

The visible symptom was elsewhere: the India annex's
discretionary clause (A5) never reached the handoff check, so
"can I extend my parental leave" was answered instead of
referred.

Fixed by over-fetching `TOP_K * 3` before the date filter and
trimming after. `OVERFETCH` in `app/desk/answer.py`.

**Neither part was wrong alone.** The filter is correct. The
retriever is correct. The composition lost results.

---

## S2 — Every annex ends with "discretionary matters"

**fixed, after two wrong fixes**

Both entity annexes end with a section reserving extensions,
sabbaticals and enhanced terms to a human. That clause is
retrieved for nearly any question about that annex, and lands
0.03–0.08 below the top match whatever was asked.

First rule — *presence anywhere in the results is decisive* —
sent **8 of 32** eval cases to a human, including "how much
parental leave do I get".

Second rule — *within a similarity margin of the top* — sent
the same 8. The margin needed to catch a real extension
request (0.015) is smaller than the noise between neighbouring
clauses in one short document.

Third rule, which holds: the discretionary clause decides when
it is the **top** result, **or** when the question itself asks
for a departure — "extend", "sabbatical", "exception", "carry
over ten days", "enhanced redundancy". Rank for the obvious
case, intent for the case where the standard-entitlement
clauses match the words better.

---

## S3 — A question about an uncovered subject still retrieves

**fixed**

This is the Week-11 bug reappearing on a new corpus, and it is
worse here. With 28 chunks there is always something at ~0.6.

Measured: in-scope questions top out at **0.718–0.885**,
out-of-scope at **0.552–0.773**. Overlapping. "What is my
salary band" scores **0.773** against an annual-leave clause.

Four of four `out_of_scope` eval cases failed — pension,
salary, expenses, medical cover — each answered with a leave
entitlement, correctly cited.

Fixed with a subject gate (`app/desk/scope.py`) checked before
retrieval. Weakness 1 in WEAKNESSES.md records what that costs.

---

## S4 — Document preambles indexed as clauses

**fixed**

The markdown loader chunked on every heading, so each
document's title heading became a chunk containing the version
banner and a note about why the edition is retained.

It indexes well on "entitled", "2024" and "leave", and was
cited as `HR-202 §HR-202 Annual and Parent` — a citation to a
preamble, pointing at no clause.

Fixed by indexing only numbered sections.

Same family as the heading-only chunks found in Week 11
(`"2 Working Hours"`, 15 characters, no body). Different
loader, same mistake.

---

## S5 — The offline judge compared against the wrong chunk

**fixed**

The judge checked the answer's words against
`retrieved[0]` — the top-ranked chunk — rather than against
the clause the answer actually cites.

C12 quotes the carry-over clause correctly while the notice
clause ranks first, so a right answer scored 25% overlap and
failed. A bug in the measuring instrument, not the system.

Fixed by comparing against the cited clauses. Worth recording
because for one run the suite was reporting a defect that did
not exist, which is the failure mode an eval suite is least
able to notice about itself.

---

## S6 — Grade and entity did not exist on the employee record

**fixed**

The Week-7 fixture had `jurisdiction` (a country string used
for statutory notice tables) but no `entity` and no `grade`.
The capstone turns on both.

Added to all six records. `jurisdiction` is left in place
because the Week-7 and Week-8 evals read it and their numbers
are reproducible against it.

Two fields now describe location — `jurisdiction: "India"` and
`entity: "IN"` — which is a wart. Accepted rather than
unified, because unifying them silently changes what Weeks 7
and 8 measured.

---

## S7 — Non-ASCII in documents broke the Windows console

**fixed**

Section symbols, em dashes and box-drawing characters in the
authored policies and the CLI crashed `python -m app.desk` on
cp1252 with a `UnicodeEncodeError`.

Fixed by keeping output ASCII. Trivial, and it would have
taken the demo down on a reviewer's machine.

---

## S8 — The desk retriever is a second retriever

**accepted**

`app/services/retriever.py` is pinned to the Week-4
collections and takes a `region` string; the desk needs a
`where` clause over `entity`.

Rather than widen the Week-4 class, I added
`app/desk/retriever.py`. Two retriever classes now exist.

Accepted on purpose: changing the Week-4 signature would make
a Week-4 number and a Week-12 number describe different code
under the same name, and `evaluation/results.md` would
silently stop being reproducible. The duplication is the
cheaper mistake.

---

## S9 — The eval does not pin clause rank

**ran out of time**

`check_clause` asserts the expected clause is cited
*somewhere*, not that it ranks first. So the §3.3-over-§3.1
failure in Weakness 2 passes the suite.

The fix is a cross-encoder rerank, which exists in this repo
(`app/services/reranker.py`) and is not wired into the desk.
Ranked first in "what I would do next" because it is the
cheapest of the three.

---

## S10 — Cost per query is zero because the key is unfunded

**accepted, documented**

Every `generation` span cost $0.00 in the eval run: the
OpenAI account returns 429, so the desk answered extractively
— returning the cited clause verbatim.

That is a real number for how the system ran, and a useless
one for what it would cost. COST.md reports both: $0.000000
measured, $0.000286 per answered query estimated from the
real payload at the real list price.
