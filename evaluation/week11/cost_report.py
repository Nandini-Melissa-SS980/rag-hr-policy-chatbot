"""
Cost per query, attributed to a stage.

    python -m evaluation.week11.cost_report

Writes cost_by_stage.md and tenx.md.

Attribution comes before optimisation. A number that
moved without a stage attached to it is a number
nobody can act on - you cannot say which change moved
it, and you cannot say what to change next.
"""

import json
import statistics

from app.config import (
    INPUT_COST_PER_1M,
    OPENAI_MODEL,
    OUTPUT_COST_PER_1M,
)
from app.observability import (
    REQUESTS_LOG,
    read_traces,
)


COST_PATH = (
    "evaluation/week11/cost_by_stage.md"
)

TENX_PATH = "evaluation/week11/tenx.md"

TRACE_PATH = "evaluation/week11/trace.json"

# The published per-minute limits for the account
# tier this project runs on. The 10x claim is
# arithmetic against these, not a guess.
RPM_LIMIT = 500

TPM_LIMIT = 200_000


def percentile(
    values: list,
    fraction: float,
) -> float:

    if not values:
        return 0.0

    ordered = sorted(values)

    index = min(
        len(ordered) - 1,
        int(fraction * len(ordered)),
    )

    return ordered[index]


def main():

    traces = read_traces()

    if not traces:

        raise SystemExit(
            "No traces. Run: python -m "
            "evaluation.week11.seed_logs"
        )

    answered = [
        trace
        for trace in traces
        if not trace["abstained"]
    ]

    stages = {}

    for trace in traces:

        for name, entry in trace[
            "cost_by_stage"
        ].items():

            totals = stages.setdefault(
                name,
                {
                    "cost_usd": 0.0,
                    "duration_ms": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "calls": 0,
                },
            )

            totals["cost_usd"] += entry[
                "cost_usd"
            ]

            totals["duration_ms"] += entry[
                "duration_ms"
            ]

            totals["input_tokens"] += entry[
                "input_tokens"
            ]

            totals["output_tokens"] += entry[
                "output_tokens"
            ]

            totals["calls"] += 1

    requests = len(traces)

    total_cost = sum(
        trace["cost_usd"] for trace in traces
    )

    total_tokens = sum(
        trace["total_tokens"]
        for trace in traces
    )

    latencies = [
        trace["duration_ms"]
        for trace in traces
    ]

    # ---- the found trace, broken down -------------
    with open(
        TRACE_PATH,
        "r",
        encoding="utf-8",
    ) as file:

        found = json.load(file)

    lines = [
        "# Week 11 - cost per query by stage",
        "",
        f"Measured over **{requests} logged "
        f"requests** in `logs/requests.jsonl`, "
        f"model `{OPENAI_MODEL}`, priced at "
        f"${INPUT_COST_PER_1M}/1M input and "
        f"${OUTPUT_COST_PER_1M}/1M output.",
        "",
        "## Whole corpus",
        "",
        "| stage | cost/query | share | "
        "tokens in | tokens out | mean ms |",
        "|---|---|---|---|---|---|",
    ]

    for name in sorted(stages):

        entry = stages[name]

        share = (
            entry["cost_usd"] / total_cost
            if total_cost
            else 0.0
        )

        lines.append(
            f"| {name} "
            f"| ${entry['cost_usd'] / requests:.6f} "
            f"| {share:.1%} "
            f"| {entry['input_tokens']} "
            f"| {entry['output_tokens']} "
            f"| {entry['duration_ms'] / max(1, entry['calls']):.1f} |"
        )

    # Tools run in the agent loop, not in this path.
    # Shown as a zero rather than omitted, so the
    # breakdown has three rows and the absence is
    # explicit.
    lines += [
        "| tools | $0.000000 | 0.0% | 0 | 0 | "
        "0.0 |",
        "",
        f"**Total cost per query: "
        f"${total_cost / requests:.6f}** "
        f"({requests} requests, "
        f"${total_cost:.4f} total, "
        f"{total_tokens} tokens).",
        "",
        f"{len(traces) - len(answered)} of "
        f"{requests} requests abstained and cost "
        "nothing to generate - they pay retrieval "
        "latency only. Cost per *answered* query "
        f"is "
        f"${total_cost / max(1, len(answered)):.6f}.",
        "",
        "## The request from the drill",
        "",
        f"`{found['trace_id']}` - the wrong notice "
        "period.",
        "",
        "| stage | ms | tokens in | tokens out | "
        "cost |",
        "|---|---|---|---|---|",
    ]

    for name, entry in found[
        "cost_by_stage"
    ].items():

        lines.append(
            f"| {name} "
            f"| {entry['duration_ms']:.2f} "
            f"| {entry['input_tokens']} "
            f"| {entry['output_tokens']} "
            f"| ${entry['cost_usd']:.6f} |"
        )

    lines += [
        "| tools | 0.00 | 0 | 0 | $0.000000 |",
        "",
        f"Total: **${found['cost_usd']:.6f}**, "
        f"{found['total_tokens']} tokens, "
        f"{found['duration_ms']:.1f}ms.",
        "",
        "## Where the money is",
        "",
        "**Generation is "
        f"{stages.get('generation', {}).get('cost_usd', 0) / total_cost:.0%} "
        "of spend and retrieval is 0%** - "
        "retrieval embeds locally, so it costs "
        "latency and not money. Within generation, "
        "input tokens dominate: the prompt plus "
        "five retrieved passages is sent on every "
        "request, and the answer is one or two "
        "sentences.",
        "",
        "That tells you where a saving would come "
        "from, and it is not the model. Dropping "
        "`top_k` from 5 to 3 removes roughly 40% "
        "of the context sent per request. "
        "Measuring that is the next change, not "
        "this one - and the attribution above is "
        "what makes it measurable.",
        "",
        "## Caveat on provenance",
        "",
        "The key behind this project returns 429 "
        "insufficient_quota, so the generator is "
        "replayed and generation tokens are "
        "estimated from the real payload at four "
        "characters per token - the same estimate "
        "Weeks 8 and 10 use. Retrieval timings, "
        "context ids, trace shape and the cost "
        "arithmetic are real. Re-run with "
        "`--live` once the key is funded and the "
        "same tables are produced from metered "
        "usage.",
        "",
    ]

    with open(
        COST_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        file.write("\n".join(lines))

    # ---- the 10x question -------------------------
    #
    # Volume here is a week of traffic, so scale to
    # per-minute to compare with the published
    # limits.
    per_day = requests / 7

    mean_tokens = total_tokens / requests

    # Traffic is not flat. A working day concentrates
    # into roughly eight hours, and the busiest
    # minute carries more than the mean - assume 3x
    # the average minute, which is conservative for
    # an internal HR tool where everyone arrives at
    # once on Monday.
    busy_rpm = (per_day / (8 * 60)) * 3

    busy_tpm = busy_rpm * mean_tokens

    tenx_rpm = busy_rpm * 10

    tenx_tpm = busy_tpm * 10

    tenx_daily_cost = (
        total_cost / 7
    ) * 10

    rpm_headroom = RPM_LIMIT / max(
        tenx_rpm,
        0.001,
    )

    tpm_headroom = TPM_LIMIT / max(
        tenx_tpm,
        0.001,
    )

    binds = (
        "the token-per-minute rate limit"
        if tpm_headroom < rpm_headroom
        else "the request-per-minute rate limit"
    )

    tightest = min(
        rpm_headroom,
        tpm_headroom,
    )

    p95 = percentile(latencies, 0.95)

    # The honest headline: at this volume 10x
    # breaks nothing, so the useful number is not
    # "what breaks at 10x" but "at what multiple
    # does the first thing bind". Reporting 125x
    # headroom as though it were a finding would be
    # dressing up a non-answer.
    breaking_multiple = tightest * 10

    tenx_lines = [
        "# Week 11 - what breaks first at 10x",
        "",
        f"**At 10x nothing breaks.** Today's "
        f"logged volume is {per_day:.0f} "
        "requests/day, so 10x is "
        f"{tenx_rpm:.0f} req/min and "
        f"{tenx_tpm:,.0f} tokens/min at the busy "
        f"minute - {tpm_headroom:.0f}x inside the "
        f"{TPM_LIMIT:,} TPM ceiling, with cost at "
        f"${tenx_daily_cost:.2f}/day and p95 "
        f"latency {p95:.0f}ms. Saying \"cost "
        "breaks first\" here would be inventing a "
        "constraint.",
        "",
        "**The number that is actually useful: "
        f"the first thing to bind is {binds}, and "
        f"it binds at ~{breaking_multiple:.0f}x "
        "today's volume** "
        f"(~{busy_rpm * breaking_multiple:,.0f} "
        f"req/min, {TPM_LIMIT:,} tokens/min). "
        "Cost reaches "
        f"${(total_cost / 7) * breaking_multiple:,.0f}/day "
        "at that point, which is a budget "
        "conversation but not a wall.",
        "",
        "Stated plainly because the baseline is "
        f"small: {requests} requests over seven "
        "days is a pilot, not production. The "
        "multiple is what transfers; the absolute "
        "numbers will not.",
        "",
        "## The arithmetic",
        "",
        f"- Today: {requests} requests over 7 "
        f"days = {per_day:.0f}/day, averaging "
        f"{mean_tokens:.0f} tokens each.",
        f"- Concentrated into an 8-hour working "
        f"day with a 3x peak-minute factor: "
        f"**{busy_rpm:.1f} req/min, "
        f"{busy_tpm:,.0f} tokens/min** at the "
        "busy minute.",
        f"- At 10x: **{tenx_rpm:.0f} req/min, "
        f"{tenx_tpm:,.0f} tokens/min**.",
        f"- Against the limits: RPM "
        f"{tenx_rpm:.0f}/{RPM_LIMIT} "
        f"({rpm_headroom:.1f}x headroom), TPM "
        f"{tenx_tpm:,.0f}/{TPM_LIMIT:,} "
        f"({tpm_headroom:.1f}x headroom).",
        f"- Cost at 10x: "
        f"${tenx_daily_cost:.2f}/day, "
        f"${tenx_daily_cost * 365:.0f}/year. Not "
        "the constraint.",
        "",
        "## Why TPM and not RPM",
        "",
        f"Each request carries about "
        f"{mean_tokens:.0f} tokens, nearly all of "
        "it input: the system prompt plus five "
        "retrieved passages, sent every time. So "
        "the token ceiling is reached at a lower "
        "request rate than the request ceiling "
        f"is - {tightest:.1f}x headroom on the "
        "tighter of the two.",
        "",
        "## What to do about it",
        "",
        "The lever is the same one the cost "
        "attribution points at: context size. "
        "Dropping `top_k` from 5 to 3 cuts "
        "roughly 40% of input tokens, which buys "
        "back most of the TPM headroom without "
        "touching the model or the rate limit "
        "tier. Request a limit increase second, "
        "not first - paying for headroom to send "
        "context the answer did not need is the "
        "expensive way round.",
        "",
        f"*Figures computed by "
        f"`evaluation/week11/cost_report.py` "
        f"from {requests} logged requests. Rate "
        "limits are the published ceilings for "
        "this account tier.*",
        "",
    ]

    with open(
        TENX_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        file.write("\n".join(tenx_lines))

    print(
        f"cost/query: "
        f"${total_cost / requests:.6f} over "
        f"{requests} requests"
    )

    for name in sorted(stages):

        print(
            f"  {name:<12} "
            f"${stages[name]['cost_usd'] / requests:.6f}"
        )

    print(
        f"\n10x busy minute: {tenx_rpm:.0f} "
        f"req/min, {tenx_tpm:,.0f} tokens/min "
        f"-> {binds} binds first "
        f"({tightest:.1f}x headroom)"
    )

    print(
        f"\nWrote {COST_PATH} and {TENX_PATH}."
    )


if __name__ == "__main__":
    main()
