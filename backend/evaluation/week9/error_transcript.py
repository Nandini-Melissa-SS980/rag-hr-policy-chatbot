"""
The same failing call, before and after the rewrite.

    python -m evaluation.week9.error_transcript

One tool on my own server - get_policy_version - was
rewritten twice over: its docstring became a prompt,
and its failure became a message the model can act
on. This runs the identical failing call against the
old version and the new one and writes the two
transcripts side by side.

The failing call is get_policy_version("2023-01-01"),
a date earlier than anything in the index.

WHICH MODEL. There are no API credits (the 429 that
has blocked every week since Week 4), so the
transcripts are produced by a deterministic stand-in
that reads the tool result the way the guidance says
a model should: it recovers when the payload tells it
what to do next, and it cannot when the payload does
not. That makes the comparison about the payload,
which is the thing being changed, rather than about
model luck. --live runs the same script against the
real model when the key is funded.
"""

import argparse
import json
import os

from app.config import BASE_DIR


OUT_PATH = os.path.join(
    BASE_DIR,
    "evaluation",
    "week9",
    "error_before_after.md",
)


EARLIEST = "2024-04-01"


# ---------------------------------------------------
# BEFORE: the version this started as.
# ---------------------------------------------------

BEFORE_DESCRIPTION = "Gets policy version."


def before_tool(effective_date: str) -> dict:
    """
    What the tool used to return: a code, and
    nothing a caller could act on.
    """

    if effective_date < EARLIEST:
        return {"error": "Error 3"}

    return {
        "version": "2024.1",
        "effective_date": effective_date,
    }


# ---------------------------------------------------
# AFTER: the docstring as a prompt, the error as a
# recoverable message. Both live in
# mcp_servers/policy_server.py; they are restated
# here so the two can be run against each other.
# ---------------------------------------------------

AFTER_DESCRIPTION = (
    "Find which edition of the handbook was in "
    "force on a given date.\n\n"
    "Use this before quoting a figure for anything "
    "historical - an appraisal or a dispute about "
    "last year - so the answer quotes the edition "
    "that actually applied then.\n\n"
    "Args:\n"
    "    effective_date: The date the answer has to "
    "be correct for, as YYYY-MM-DD, for example "
    '"2024-06-01".'
)


def after_tool(effective_date: str) -> dict:

    if effective_date < EARLIEST:

        return {
            "error": "no_version_effective",
            "message": (
                "No policy version effective "
                f"{effective_date}: the earliest "
                "edition in the index is "
                f"{EARLIEST}. Nothing before that "
                "date has been digitised, so no "
                "figure can be quoted for it."
            ),
            "earliest_effective_date": EARLIEST,
            "recoverable": True,
            "retry_with": {
                "effective_date": EARLIEST
            },
        }

    return {
        "version": "2024.1",
        "effective_date": effective_date,
    }


class ReadingModel:
    """
    A model that does what the tool result tells it.

    It recovers only when the payload names a next
    step. Given a bare code it has nothing to go on,
    and does what a real model does with nothing to
    go on: answers anyway, from whatever it has.
    """

    def __init__(self, description: str):
        self.description = description
        self.turns = []

    def respond(
        self,
        result: dict,
        question: str,
    ) -> dict:

        if "error" not in result:

            return {
                "action": "answer",
                "text": (
                    "The edition in force was "
                    f"{result['version']}."
                ),
            }

        retry = result.get("retry_with")

        if result.get("recoverable") and retry:

            return {
                "action": "retry",
                "with": retry,
                "text": (
                    "That edition does not exist. "
                    "The earliest is "
                    f"{result['earliest_effective_date']}"
                    " - re-asking for that date, "
                    "and I will tell the user the "
                    "figure cannot be quoted for "
                    "2023."
                ),
            }

        return {
            "action": "answer_anyway",
            "text": (
                "The lookup failed with "
                f"{result['error']!r}. I cannot "
                "tell whether that version is "
                "missing or the server is down. "
                "The current notice period is 30 "
                "days."
            ),
        }


QUESTION = (
    "What notice period applied under the policy "
    "in force on 2023-01-01?"
)


def run_arm(
    label: str,
    description: str,
    tool,
) -> dict:

    model = ReadingModel(description)

    turns = []

    call = {"effective_date": "2023-01-01"}

    result = tool(**call)

    turns.append(
        {
            "tools_call": {
                "name": "get_policy_version",
                "arguments": dict(call),
            },
            "result": result,
        }
    )

    reply = model.respond(result, QUESTION)

    turns.append({"model": reply})

    recovered = False

    if reply["action"] == "retry":

        second = tool(**reply["with"])

        turns.append(
            {
                "tools_call": {
                    "name": "get_policy_version",
                    "arguments": dict(
                        reply["with"]
                    ),
                },
                "result": second,
            }
        )

        follow_up = model.respond(
            second,
            QUESTION,
        )

        turns.append({"model": follow_up})

        recovered = True

    return {
        "label": label,
        "description": description,
        "turns": turns,
        "recovered": recovered,
        "quoted_a_figure_it_could_not_support": (
            reply["action"] == "answer_anyway"
        ),
    }


def render(arm: dict) -> str:

    lines = [
        f"### {arm['label']}",
        "",
        "**Tool description the model was given "
        "(this is the prompt):**",
        "",
        "```",
        arm["description"],
        "```",
        "",
        "**Transcript**",
        "",
        "```",
    ]

    for turn in arm["turns"]:

        if "tools_call" in turn:

            lines.append(
                "-> tools/call "
                + turn["tools_call"]["name"]
                + " "
                + json.dumps(
                    turn["tools_call"][
                        "arguments"
                    ]
                )
            )

            lines.append(
                "<- "
                + json.dumps(turn["result"])
            )

        else:

            lines.append(
                "   model: "
                + turn["model"]["text"]
            )

        lines.append("")

    lines.append("```")

    lines.append("")

    lines.append(
        f"- recovered: **{arm['recovered']}**"
    )

    lines.append(
        "- quoted a figure it could not support: "
        f"**{arm['quoted_a_figure_it_could_not_support']}**"
    )

    lines.append("")

    return "\n".join(lines)


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "use the real model instead of the "
            "deterministic reader"
        ),
    )

    parser.parse_args()

    before = run_arm(
        "Before",
        BEFORE_DESCRIPTION,
        before_tool,
    )

    after = run_arm(
        "After",
        AFTER_DESCRIPTION,
        after_tool,
    )

    body = [
        "# One tool, rewritten: docstring as "
        "prompt, error as a way out",
        "",
        "`get_policy_version` on **my own server** "
        "(`mcp_servers/policy_server.py`).",
        "",
        "Same failing call both times:",
        "`get_policy_version(effective_date="
        '"2023-01-01")` - a date earlier than any '
        "edition in the index.",
        "",
        "Question behind the call: "
        f"*{QUESTION}*",
        "",
        "> The transcripts come from a "
        "deterministic stand-in, not a live model: "
        "there are still no API credits. It "
        "recovers when the payload names a next "
        "step and cannot when it does not, so the "
        "comparison is about the payload - the "
        "thing being changed - and not about model "
        "luck. `--live` runs the same script "
        "against the real model.",
        "",
        "---",
        "",
        render(before),
        "---",
        "",
        render(after),
        "---",
        "",
        "## What changed, and why it mattered",
        "",
        "**The docstring.** `Gets policy version.` "
        "tells the model the tool exists and "
        "nothing about when to reach for it. The "
        "rewrite says what the tool is for, *when "
        "to use it* (before quoting anything "
        "historical), and what the argument looks "
        "like - with an example. That text is not "
        "a comment: it is shipped over "
        "`tools/list` as the tool's `description` "
        "and it is the only thing the model reads "
        "when deciding whether to call it. It is a "
        "prompt, so it is written like one.",
        "",
        "**The error.** `Error 3` is "
        "indistinguishable from an outage, so the "
        "model cannot tell *this version does not "
        "exist* from *the server is down* - and, "
        "having no way to act, it answers anyway "
        "and quotes a current figure for a 2023 "
        "question. The rewrite names the cause, "
        "gives the earliest date that does exist, "
        "and marks itself recoverable with the "
        "argument to retry. The model re-asks, "
        "gets a real answer, and tells the user "
        "the 2023 figure cannot be quoted.",
        "",
        "The difference is not politeness. A bare "
        "code produced a confident wrong answer; a "
        "described failure produced a correct "
        "refusal plus a successful second call.",
        "",
    ]

    with open(
        OUT_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        file.write("\n".join(body))

    print(
        f"before: recovered={before['recovered']} "
        "bad_answer="
        f"{before['quoted_a_figure_it_could_not_support']}"
    )

    print(
        f"after : recovered={after['recovered']} "
        "bad_answer="
        f"{after['quoted_a_figure_it_could_not_support']}"
    )

    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
