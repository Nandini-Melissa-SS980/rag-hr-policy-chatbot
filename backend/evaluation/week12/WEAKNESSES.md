# Top 3 known weaknesses

Written down before anyone asked. These are the three things I
would attack first if the system went to 4,000 employees, and
the three I would raise myself in a grievance meeting before
the other side did.

---

## 1. The scope gate is a hand-maintained deny list

**What it is.** `app/desk/scope.py` refuses questions about
six named subjects the corpus does not cover — pension,
salary, expenses, medical cover, training budget, equipment —
by matching the question text. Everything else falls through
to the retrieval score.

**Why it exists.** A threshold cannot do this job, and the
measurement says so. On the desk index the top retrieval score
for a question this corpus answers runs **0.718–0.885**. For
one it does not: **0.552–0.773**. The ranges overlap. "What is
my salary band" scores **0.773** against an annual-leave
clause — higher than "what notice do I have to give" at
0.718, which is a question the system should answer. No cut
separates them.

**Why it is a weakness.** It is a list of what we thought of.
A seventh uncovered subject — visa sponsorship, say, or
bereavement leave — is not on it, and the system will answer
that question from the nearest leave clause at ~0.6 with a
confident citation. The failure mode is invisible: the
citation resolves, the version is right, the entity is right,
and the answer is about something else entirely.

**What would fix it.** An entailment check between the
question and the retrieved clause, rather than a similarity
score or a word list. That is a model call per request and
roughly doubles the cost per query, which is why it is
ranked next rather than done.

---

## 2. Retrieval ranks the wrong clause of the right document

**What it is.** The system cites the clause it quotes, so the
citation is honest, but the clause it quotes is not always the
one that best answers the question.

**The example, from the eval run.** "What was I entitled to
for parental leave in March 2024?" correctly filters to the
2024 edition — every citation is `v2024.1`, the superseded-
version filter works — and then ranks **§3.3 Notice for
Parental Leave** above **§3.1 Parental Leave — Primary
Carer**. The answer is about notice periods. The citation
says §3.3. Nothing is fabricated, and the employee still gets
the wrong information.

**Why it happens.** §3.3 contains "parental leave" and
"notice" and "weeks", which is most of the question. §3.1
contains "primary carer" and the figure. Bi-encoder
similarity does not know which of those answers "how much".

**Why it is a weakness.** The eval suite does not catch it.
`check_clause` asserts the expected clause appears *somewhere*
in the citations, deliberately, because asserting rank 1 would
fail cases whose citation is correct. So this mode passes the
suite and would reach an employee.

**What would fix it.** A cross-encoder rerank over the top 6,
which exists in this repo already (`app/services/reranker.py`,
Week 4) and is not wired into the desk. That is the cheapest
of the three fixes.

---

## 3. The judge is me, and neither of us is an employment lawyer

**What it is.** The offline judge checks that the answer's
substantive words appear in the clause it cites. It agrees
with the deterministic assertions **100%** on this run
(n=20, 12 cases not judged because only answered cases are
judged for grounding).

**Why that number is weaker than it looks.** Agreement with
the assertions is not agreement with the truth. Both the
assertions and the judge were written by me against a corpus
I also wrote. A clause that is correctly retrieved, correctly
versioned, correctly scoped to the entity and correctly quoted
will pass every check in this suite **even if the policy it
quotes is legally wrong**, because nothing here checks the
policy against employment law.

The 2024 and 2025 parental-leave figures, the India
Maternity Benefit Act reference, the UK statutory notice
ladder: all authored fixtures. Plausible, not verified.

**Why it is a weakness.** The brief's hostile question is
exactly right. "Your judge agreed with your labels 87% of the
time. You are not an employment lawyer and neither is your
judge." The honest answer is that this suite measures whether
the system faithfully reports what the documents say. It
measures nothing about whether the documents are right. For a
grievance meeting you would need the policy set signed off by
someone who is liable for it, and then this suite tells you
the system is quoting that set correctly.

**What would fix it.** Hand labels from an HR business partner
on a sample of 50 answers, reported as agreement against
*their* labels rather than against my own assertions. Until
then the number to quote is "100% agreement with my own
rules", said in those words.

---

## What I am not claiming

- Not multi-turn. Every case is one question, no history.
- Not tested against paraphrase. Each question is asked one
  way; a rewording that retrieves differently is not covered.
- Not load tested. The 10x plan is arithmetic over measured
  per-request numbers, not a load test.
- The MCP hop is exercised separately from the eval cases,
  which run in-process.
