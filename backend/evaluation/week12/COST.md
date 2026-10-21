# Cost per question, and the 10x plan

Measured over the 192 traces in `logs/week12_eval.jsonl`
(32 eval cases x 6 runs during the build), model `gpt-5-mini`
at the list price in `backend/.env`: $0.25/1M input,
$2.00/1M output.

---

## Cost per question

| | |
|---|---|
| **Measured** | **$0.000000** |
| **Estimated, funded** | **$0.000179** per question |
| Per *answered* question | $0.000286 |

**The measured number is zero and that is not a good thing.**
The OpenAI account behind this project returns 429
`insufficient_quota`, so every `generation` span cost nothing
because no model was called — the desk answered extractively,
returning the cited clause verbatim. Honest, and useless for
budgeting.

The estimate is built from the real payload at the real list
price: prompt v2 is 276 tokens, three retrieved clauses
average 229, the question averages ~10, and an answer is
~80 output tokens. 505 in + 80 out = **$0.000286** per
answered question.

**62.5% of questions are answered** (120 of 192). The other
72 refuse or hand off before the model is reached and cost
nothing to generate. So cost per question overall is
`$0.000286 x 0.625 = $0.000179`.

### By stage

| stage | cost/query | share | mean latency |
|---|---|---|---|
| retrieval | $0.000000 | 0% | 341 ms |
| generation | $0.000179 | 100% | 0 ms (not called) |
| tools | $0.000000 | 0% | 0.09 ms |

Retrieval costs latency, not money — the embedding model runs
locally. Every penny is generation, and within generation it
is input tokens: the prompt plus three clauses is sent on
every request and the answer is two sentences.

**That is where a saving would come from, and it is not the
model.** Dropping from three cited clauses to two removes
~76 input tokens, about 15% of the input. Not done, because
the third clause is what lets an answer say what the general
case is when the entity annex overrides it.

---

## At 10x — what breaks first

The client fields **~700 policy questions a month** across six
HR staff. 10x is 7,000/month.

| | today | 10x |
|---|---|---|
| per month | 700 | 7,000 |
| per working day | 32 | 318 |
| mean req/min (8h day) | 0.07 | 0.66 |
| peak minute (3x mean) | 0.2 | **2.0** |
| monthly spend | $0.13 | **$1.25** |

### Nothing breaks at 10x, and saying otherwise would be inventing a constraint

The first thing to bind is **single-worker retrieval
throughput**, and it binds at roughly **89x** today's volume,
not 10x.

Retrieval is 341 ms mean and the embedding model is local and
single-threaded, so one worker serves **176 req/min**. The
10x peak minute needs 2. That is **89x headroom** on the
tightest resource in the system.

Cost reaches **$1.25/month** at 10x and **$11/month** at 89x.
Neither is a budget conversation.

### The number that does transfer

**At ~89x today's volume (≈62,000 questions/month) a single
worker saturates on retrieval latency.** The fix is horizontal
— the desk is stateless, so it is a second process — and the
embedding model is the thing to move behind a shared service
at that point, not the LLM.

### What this is not

Arithmetic over measured per-request numbers, not a load test.
It assumes the 341 ms retrieval mean holds under concurrency,
which it will not exactly: the model is loaded per process and
competes for CPU. The multiple is what transfers; the absolute
numbers will not.

---

## Ranked next, with costs

1. **Cross-encoder rerank over the top 6.** Fixes Weakness 2
   (right document, wrong clause). The reranker already
   exists in this repo from Week 4 and is not wired into the
   desk. Cost: ~80 ms per request, $0. Cheapest real
   improvement available.

2. **Entailment check between question and clause.** Replaces
   the hand-maintained deny list in Weakness 1 with something
   that generalises to the seventh uncovered subject. Cost:
   one extra model call, roughly doubling cost per query to
   ~$0.00036. Worth it at any volume this client has.

3. **Hand labels from an HR business partner.** 50 answers
   scored by someone who is liable for the policy set, so
   the judge-agreement number means something outside this
   repo. Cost: a half-day of an HRBP's time, $0 in compute,
   and it is the only item here that makes the numbers
   defensible in a grievance meeting.
