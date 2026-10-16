# Week 11 - prompt version bump, canary and rollback

## The bump

| | |
|---|---|
| **From** | `v1` |
| **To** | `v2` |
| **Change** | one added rule (rule 4): the retrieved context must be about the subject the question asks about, or refuse |
| **File** | [app/services/prompts.py](../../app/services/prompts.py) |
| **Shipped by** | `CURRENT_PROMPT_VERSION = "v2"` |
| **Evidence** | 18/30 -> 22/30, drill cases 0/3 -> 3/3, `BROKEN: []` |

v1 is kept in the file, not deleted. A trace logged last Tuesday says `prompt_version: v1`, and that has to keep resolving to the text that actually ran.

## Canary

**Route 10% of traffic to v2 for 24 hours, and watch the abstention rate on that slice: it should rise by roughly 2-4 points, not more.** The fix works by refusing more, so some rise is the change landing; a jump past ~10 points means the topic gate is overshooting and swallowing answerable questions, which is exactly how E21 broke in testing.

**Second signal, checked at the same time: `--answer` searches for notice-shaped replies on the v2 slice should return zero rows.** If any v2 trace still quotes a notice period, the gate is not firing in production regardless of what the suite said.

```bash
python -m evaluation.week11.logcli --prompt-version v2 --answer "notice"   # expect 0
python -m evaluation.week11.logcli --prompt-version v2                     # abstention rate
```

## Rollback

**Set `CURRENT_PROMPT_VERSION = "v1"` in [app/services/prompts.py](../../app/services/prompts.py) and redeploy - one line, no data migration, no index rebuild.** Traces already written keep their own `prompt_version`, so the log stays readable across the revert and a post-mortem can still tell which requests ran under which text.

**Roll back if abstention on the v2 slice rises past 10 points or any answerable-question complaint arrives from the canary group**; accept the known trade that notice-period questions return to being answered wrongly until a fix ships, because a confidently wrong policy answer is worse than a refusal.

## Known follow-up, deliberately not bundled here

The deeper fix is the retrieval gate, not the prompt. `has_good_match` compares the top score against 0.45, and the failing request scored 0.73 on a passage about annual leave - the threshold catches *nothing retrieved*, never *nothing relevant retrieved*. A relative gate, or a margin between the top score and the rest, would catch this class before the model is called at all.

Not done this week because it changes behaviour on every request rather than on one topic, so it needs its own before/after over the whole suite. Shipping it alongside the prompt bump would have made the 18 -> 22 unattributable.
