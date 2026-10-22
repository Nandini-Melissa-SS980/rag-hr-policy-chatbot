# Week 11 - what breaks first at 10x

**At 10x nothing breaks.** Today's logged volume is 28 requests/day, so 10x is 2 req/min and 1,676 tokens/min at the busy minute - 119x inside the 200,000 TPM ceiling, with cost at $0.08/day and p95 latency 23ms. Saying "cost breaks first" here would be inventing a constraint.

**The number that is actually useful: the first thing to bind is the token-per-minute rate limit, and it binds at ~1193x today's volume** (~210 req/min, 200,000 tokens/min). Cost reaches $10/day at that point, which is a budget conversation but not a wall.

Stated plainly because the baseline is small: 197 requests over seven days is a pilot, not production. The multiple is what transfers; the absolute numbers will not.

## The arithmetic

- Today: 197 requests over 7 days = 28/day, averaging 953 tokens each.
- Concentrated into an 8-hour working day with a 3x peak-minute factor: **0.2 req/min, 168 tokens/min** at the busy minute.
- At 10x: **2 req/min, 1,676 tokens/min**.
- Against the limits: RPM 2/500 (284.3x headroom), TPM 1,676/200,000 (119.3x headroom).
- Cost at 10x: $0.08/day, $31/year. Not the constraint.

## Why TPM and not RPM

Each request carries about 953 tokens, nearly all of it input: the system prompt plus five retrieved passages, sent every time. So the token ceiling is reached at a lower request rate than the request ceiling is - 119.3x headroom on the tighter of the two.

## What to do about it

The lever is the same one the cost attribution points at: context size. Dropping `top_k` from 5 to 3 cuts roughly 40% of input tokens, which buys back most of the TPM headroom without touching the model or the rate limit tier. Request a limit increase second, not first - paying for headroom to send context the answer did not need is the expensive way round.

*Figures computed by `evaluation/week11/cost_report.py` from 197 logged requests. Rate limits are the published ceilings for this account tier.*
