# Week 11 - cost per query by stage

Measured over **197 logged requests** in `logs/requests.jsonl`, model `gpt-5-mini`, priced at $0.25/1M input and $2.0/1M output.

## Whole corpus

| stage | cost/query | share | tokens in | tokens out | mean ms |
|---|---|---|---|---|---|
| generation | $0.000280 | 100.0% | 172892 | 5920 | 0.0 |
| retrieval | $0.000000 | 0.0% | 0 | 0 | 44.3 |
| tools | $0.000000 | 0.0% | 0 | 0 | 0.0 |

**Total cost per query: $0.000280** (197 requests, $0.0551 total, 178812 tokens).

0 of 197 requests abstained and cost nothing to generate - they pay retrieval latency only. Cost per *answered* query is $0.000280.

## The request from the drill

`R-7f3c1a9e4d2b` - the wrong notice period.

| stage | ms | tokens in | tokens out | cost |
|---|---|---|---|---|
| retrieval | 15.02 | 0 | 0 | $0.000000 |
| generation | 0.02 | 942 | 32 | $0.000300 |
| tools | 0.00 | 0 | 0 | $0.000000 |

Total: **$0.000300**, 974 tokens, 15.1ms.

## Where the money is

**Generation is 100% of spend and retrieval is 0%** - retrieval embeds locally, so it costs latency and not money. Within generation, input tokens dominate: the prompt plus five retrieved passages is sent on every request, and the answer is one or two sentences.

That tells you where a saving would come from, and it is not the model. Dropping `top_k` from 5 to 3 removes roughly 40% of the context sent per request. Measuring that is the next change, not this one - and the attribution above is what makes it measurable.

## Caveat on provenance

The key behind this project returns 429 insufficient_quota, so the generator is replayed and generation tokens are estimated from the real payload at four characters per token - the same estimate Weeks 8 and 10 use. Retrieval timings, context ids, trace shape and the cost arithmetic are real. Re-run with `--live` once the key is funded and the same tables are produced from metered usage.
