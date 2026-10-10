# Week 10 - injected worker failure

## What was injected

On case **E13** ("How do I book time off?") the policy retrieval worker returns **HTTP 500 retrieval backend unavailable** instead of a result. The eligibility worker and the manager are untouched, and the other nine cases run normally.

The failure is injected in `run_orchestrator(fail_policy_worker=True)`. Nothing downstream is scripted: what the manager does about it is whatever the manager does.

## What the orchestrator actually did

**DEGRADED** - named what it could not establish and did not supply a policy figure.

Hand-offs for this case:

```
[ 1] manager      -> policy       total=     0 FAILED  HTTP 500 retrieval backend unavailable
[ 2] workers      -> manager      total=   331 ok
```

Manager's answer:

> I could not establish this: the policy retrieval specialist failed and no policy text was returned, so there is nothing I can cite.

Sources cited: `[]`

Scored: FAIL (assertions FAIL, judge -)

## The one-line answer

The orchestrator **degraded**: named what it could not establish and did not supply a policy figure.

## What the single agent did on the same case

The single agent has no worker to lose, so there is nothing to inject into it. For reference it scored **PASS** on E13 with 2117 tokens. The comparison in the race table is the clean run; this case is reported separately so an injected failure does not quietly deflate the squad's pass rate without the reader knowing.

## Provenance

- model: `replayed_plans`
- handbook: `live_retriever`
- judge: `offline_judge`

The OpenAI key behind this project returns 429 insufficient_quota, so the model is replayed from authored plans and the judge is the offline one. The loop, the tools, the index, the token counting, the latency and the cost arithmetic are real and are identical on both arms. `--live` swaps in the real model and the Week-6 judge and scores the same way.
