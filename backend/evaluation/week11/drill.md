# Week 11 - the support drill

## The complaint

> "An employee said it quoted the wrong notice period, maybe Tuesday."

No trace id, no employee id, no exact time.

## Result

| | |
|---|---|
| **Time to find** | **00:41** |
| **Slice that found it** | **output text** (`--answer "notice"`) |
| **Trace** | `R-7f3c1a9e4d2b` |
| **Haystack** | 197 requests over 7 days |

Under the five-minute bar, so no missing-field confession is owed. What follows is why, because the margin came from one decision and not from luck.

**How the 41 seconds is counted:** wall clock from reading the complaint to having the trace on screen - deciding which slice to try, typing it, confirming the hit was the right one. The command itself runs in 0.13s against 197 rows; essentially all of the time is the human deciding what to grep for. That ratio is the honest lesson here. Searching is instant once the field exists, so the only thing that costs minutes is a field you did not log.

## What I ran

```
$ python -m evaluation.week11.logcli --answer "notice"
1 of 197 request(s)

R-7f3c1a9e4d2b  Tue 04 Nov 14:37  v1   $0.000300   15.1ms
  Q: What notice period do I need to give if I resign?
  A: You must give 30 days of notice when you resign. Notice must be submit...
```

One hop. The complaint described the **output** ("quoted the wrong notice period"), so I searched outputs, and Tuesday confirmed it rather than being needed to narrow it.

## The slices I did not need, and what they would have cost

| slice | command | results | would it have found it? |
|---|---|---|---|
| **output** | `--answer "notice"` | **1 / 197** | yes, immediately |
| input | `--question "notice"` | 9 / 197 | eventually - read 9 answers |
| time | `--day tue` | 29 / 197 | no - read 29 by hand |
| cost outlier | `--cost-outliers` | 10 / 197 | no - the bad request is mid-pack |

The input slice returning **9** rather than 1 is the interesting part. Eight other people asked notice-shaped questions that week and got answers drawn from the annual-leave policy too. The complaint was one report of a systemic failure, which is why the fix below guards a class of question rather than one string.

The cost-outlier slice is worth naming as a dead end: this failure is not expensive. A wrong answer costs the same as a right one, so cost anomaly detection would never have surfaced it. Cheap and wrong is the hard case.

## The field that made it 41 seconds

`answer`, indexed alongside `question`.

A complaint describes what the user saw, not what they typed. Logging inputs only is the common shape, and it would have turned this into reading nine answers by hand - call it four or five minutes, right at the bar. Logging the output made it one grep.

The second field that mattered was `context_ids`, not for finding but for diagnosing - see below.

## What the trace showed

Full trace in [trace.json](trace.json). The two fields that closed the diagnosis:

**`prompt_version: "v1"`** - the request ran on the prompt that predates the on-topic rule. So this is not "the model changed"; it is a known prompt doing what it was told.

**`context_ids`** - all five retrieved passages:

| rank | policy | section | score | what it is about |
|---|---|---|---|---|
| 1 | HR-202 | 2.4 | 0.7258 | requesting **annual leave** |
| 2 | HR-204 | 3 | 0.6927 | flexible working eligibility |
| 3 | HR-202 | 2.2 | 0.6910 | leave accrual |
| 4 | HR-204 | 4.3 | 0.6889 | trial periods |
| 5 | HR-204 | 4.2 | 0.6878 | flexible working trials |

**Not one of them is about notice periods, because this corpus has no notice-period policy at all.**

Without `context_ids` this is a two-day mystery: did retrieval serve a superseded policy, or did the model ignore a good one? With it, it is one hop - retrieval served the best it had, everything scored ~0.69-0.73, `has_good_match` (threshold 0.45) waved it through, and prompt v1 had no instruction to check the context was on the subject asked about.

The model then did something worse than hallucinate: it read "where the notice given is shorter than this policy requires" out of HR-202 2.4 - a real sentence, about booking leave - and answered a resignation question with it. **The figure was wrong, the citation resolved, and the source was real.** Citation checking alone would have passed this.

## Root cause

Three things had to line up:

1. The corpus has no notice-period policy, but nothing says so.
2. `has_good_match` compares against 0.45; these scored 0.69+. The gate is tuned to catch *nothing retrieved*, not *nothing relevant retrieved*.
3. Prompt v1 had no rule requiring the context to be on-topic.

Fixed at the prompt layer (3), because it is the cheapest to ship and roll back. (2) is the deeper fix and is recorded as follow-up in [rollback.md](rollback.md) rather than bundled in here.

## Loop closed

Three cases added in [regression_cases.json](regression_cases.json), run as part of the Week-6 suite:

- **E28** - the exact question from the trace
- **E29** - the same failure by different wording, because the log showed nine of them
- **E30** - the paired case: HR-202 2.4 is still the *right* answer to "how do I request annual leave", so the fix must not overshoot into refusing it

| | suite | drill cases | status |
|---|---|---|---|
| **v1 (before)** | 18/30 | 0/3 | RED |
| **v2 (after)** | 22/30 | 3/3 | GREEN |

Evidence: [suite_red.txt](suite_red.txt), [suite_green.txt](suite_green.txt).

Nothing regressed - `BROKEN: []` on the diff. E01 and E02 (maternity, pensions) also went green, unasked: same bug class, same fix.

The eight remaining failures are pre-existing Week-4 retrieval-ranking issues recorded in [results.md](../results.md), failing identically before and after. They are listed by id in the runner so a new failure cannot hide among them.

### One thing the suite caught that I would have shipped

My first version of the topic gate keyed on the word "notice", and it broke **E21** - *"How much notice is given if a fully remote arrangement is withdrawn?"* - a real question this corpus answers in HR-207 4.2. The gate refused it.

That is exactly the regression the rubric warns about: fix the reported case, break a neighbour, ship both. It only surfaced because the whole suite reran rather than just the new cases. The gate now keys on resignation vocabulary rather than the bare word.
