# Week 10 - race table

Single agent vs policy squad (manager + policy worker + eligibility worker).

## The ten cases

The same ten Week-6 cases from `evaluation/eval_set.json`, run through both arms with the same judge and the same pass rule. No case was written for this week.

| id | mode | question |
|---|---|---|
| E01 | out_of_scope | How much maternity leave do I get? |
| E04 | out_of_scope | How do I claim travel expenses? |
| E07 | empty_chunk | How many days of annual leave do I get? |
| E08 | empty_chunk | What are my standard working hours? |
| E11 | empty_chunk | Can I carry unused leave into next year? |
| E13 | wrong_policy | How do I book time off? |
| E16 | wrong_policy | Do I get paid extra for staying late? |
| E17 | wrong_policy | How long must I work here before I can request flexible working? |
| E20 | unciteable | When do I have to report an absence? |
| E22 | near_miss | How long is my lunch break? |

## The four numbers

| metric | single agent | policy squad |
|---|---|---|
| Pass rate | 80% | 70% |
| p50 latency (s) | 0.016 | 0.016 |
| p99 latency (s) | 0.031 | 0.016 |
| p50 model calls | 2 | 3 |
| p99 model calls | 2 | 4 |
| Total tokens | 18339 | 14940 |
|   of which input | 17562 | 13671 |
|   of which output | 777 | 1269 |
| Cost per question (USD) | $0.000595 | $0.000596 |

Pass rate is `8/10` for the single agent and `7/10` for the squad.

### The injected failure is inside those numbers

`E13` is the case where the policy worker is deliberately made to return a 500, so the squad loses it by construction. Charging the pattern for an injection would be unfair, so here are the same arms over the nine clean cases:

| metric | single agent | policy squad |
|---|---|---|
| Pass rate (9 clean cases) | 0.778 (7/9) | 0.778 (7/9) |
| Total tokens (9 clean cases) | 16222 | 14609 |
| Cost per question (9 clean cases) | $0.000584 | $0.000644 |

**On the nine cases where nothing was broken the two arms tie on quality.** Neither the ten-case nor the nine-case reading shows the squad answering better than the single agent on a single question.

Note which direction the injection moves the cost column. A worker that fails early is **cheap**: the squad's E13 run cost 331 tokens because it never retrieved anything. That drags the squad's ten-case average down to a false tie with the single agent. Over the nine clean cases the squad is **10% more expensive per question**. A failure that makes an arm look cheaper is exactly the kind of thing a headline average hides, which is why both are printed.

### Read the latency rows with care

**Under replay the two latency rows measure this laptop, not the system.** There is no network call to time, so a p50 of a few milliseconds is replay overhead and nothing else. They are reported because the rubric asks for them, and they will mean something under `--live`.

The model-call rows are the honest offline proxy: they count the sequential round trips each arm makes, which is what the latency is actually made of once the endpoint is real. The squad makes **30** calls across the ten cases against the single agent's **20** - 1.5x the round trips, and they are sequential, because the eligibility worker's brief contains the policy worker's output.

## Multiplier

Context re-send multiplier: 0.8x (14940 multi / 18339 single tokens). Largest share: "manager -> policy resend, 69.7% of all multi-arm tokens" (10408 tokens, of which 182 are context the manager already held).

### Why the multiplier is below 1.0, and why that is not a win

The squad sends **22% fewer input tokens** than the single agent, for a reason that has nothing to do with teamwork: each specialist carries a narrower tool schema. The single agent is handed all three tool definitions on every lap (444 tokens); the policy worker is handed one (139). Over ten cases that discount outweighs everything the hand-offs add.

It does not survive contact with the cost column. The squad produces **63% more output tokens**, because three components each emit a JSON answer where the single agent emits one. Output is priced at $2.0/1M against $0.25/1M for input - 8x - so the input saving and the output penalty very nearly cancel, and cost per question comes out $0.000595 single against $0.000596 multi. The squad costs the same and answers no better.

The honest reading of the multiplier is therefore: **on this test set the re-send cost is real but small, because eight of the ten cases never invoke the second specialist at all.** A test set where every case needed both workers would push it well above 1.0. That is measured below, not assumed: see the hand-off table, where the one case that does use both workers (E17) costs 2,599 tokens against the single agent's 2,087.

## Token share by hand-off (multi arm)

| hand-off | tokens | of which re-sent | share |
|---|---|---|---|
| manager -> policy | 10408 | 182 | 69.7% |
| workers -> manager | 3885 | 994 | 26.0% |
| manager -> eligibility | 647 | 121 | 4.3% |

## How these numbers were produced

- model: `replayed_plans`
- handbook: `live_retriever`
- judge: `offline_judge`
- prices: $0.25/1M in, $2.0/1M out

The OpenAI key behind this project returns 429 insufficient_quota, so the model is replayed from authored plans and the judge is the offline one. The loop, the tools, the index, the token counting, the latency and the cost arithmetic are real and are identical on both arms. `--live` swaps in the real model and the Week-6 judge and scores the same way.
