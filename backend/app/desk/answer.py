"""
The Policy Answer Desk.

One function, `answer_policy_question`, joining the pieces:

    resolve   grade + entity + as_of, from the employee record
    retrieve  filtered to that entity, that edition
    rank      the entity annex above the handbook
    decide    answer, refuse, or hand to an HR business partner
    cite      clause + version + effective date
    log       one trace id across every hop

ORDER MATTERS
-------------
Resolution happens before retrieval, not after. The brief's
central failure is an entitlement answered from a correctly
retrieved chunk that belongs to a different employee - right
clause, wrong person - and the only defence is to know who is
asking before deciding what to read.

WHAT IT REFUSES
---------------
Three things, and the distinction between them is the product:

    out of scope     no policy covers this -> refuse
    discretionary    a policy covers it and says a human
                     decides -> hand to an HRBP
    about someone    a question about a named colleague's
        else         entitlement -> refuse without confirming
                     or denying anything about them

A confident guess on a discretionary matter is the failure HR
is most exposed to, so the handoff is preferred over an answer
whenever the retrieved policy says a human decides.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date

from app.desk.resolution import (
    Subject,
    annex_wins,
    citation_of,
    filter_in_force,
    format_citation,
    policy_filter,
    resolve_subject,
)
from app.observability import Recorder
from app.services.prompts import (
    CURRENT_PROMPT_VERSION,
)


TOP_K = 6

# How many extra candidates to pull before the edition window
# is applied. Sized so that a corpus holding two editions of
# every clause still leaves TOP_K in-force results.
OVERFETCH = 3

# How far below the best match a "discretionary matters"
# clause may sit and still decide the answer. Tuned on the
# demo set: A5 sits ~0.20 below a direct entitlement match,
# and within ~0.05 when the question really is about an
# extension or a sabbatical.
DISCRETION_MARGIN = 0.08

# Below this the retriever has not found the subject at all.
# Deliberately the Week-6 threshold, so the one number that
# governs abstention did not quietly change for the capstone.
MIN_SCORE = 0.45


# A policy clause that says a human decides. These are phrases
# the annexes actually use, not a general-purpose list.
DISCRETIONARY = re.compile(
    r"discretionar|refer(?:red)? to an HR business partner"
    r"|must be referred|at the company's discretion",
    re.IGNORECASE,
)

# Asking about a named colleague. The guardrail must refuse
# without confirming the colleague exists, has a grade, or
# works here at all - the shape of the refusal leaks as surely
# as its content.
THIRD_PARTY = re.compile(
    r"\b(?:what|how much|does|is|are)\b[^?]{0,60}\b"
    r"(?:colleague|coworker|co-worker|teammate|my manager|"
    r"someone else|another employee|E-\d{4}'s)\b",
    re.IGNORECASE,
)

OTHER_EMPLOYEE_ID = re.compile(
    r"\bE-\d{4}\b",
    re.IGNORECASE,
)


@dataclass
class DeskAnswer:

    status: str

    answer: str

    citations: list = field(
        default_factory=list
    )

    subject: dict = field(default_factory=dict)

    retrieved: list = field(
        default_factory=list
    )

    trace_id: str = ""

    handoff: dict | None = None

    def as_dict(self) -> dict:

        return {
            "status": self.status,
            "answer": self.answer,
            "citations": self.citations,
            "subject": self.subject,
            "retrieved": self.retrieved,
            "trace_id": self.trace_id,
            "handoff": self.handoff,
        }


def asks_about_someone_else(
    question: str,
    employee_id: str,
) -> bool:
    """
    Whether this question is about a person other than the
    asker.
    """

    mentioned = {
        match.group(0).upper()
        for match in OTHER_EMPLOYEE_ID.finditer(
            question
        )
    }

    if mentioned - {employee_id.upper()}:
        return True

    return bool(THIRD_PARTY.search(question))


def is_discretionary(
    results: list[dict],
) -> dict | None:
    """
    The retrieved clause that says a human decides, when it
    is the clause that actually answers the question.

    Read off the policy text rather than off a keyword list
    over the question, because whether something is
    discretionary is a property of the policy, not of how the
    question was phrased.

    THE MARGIN EXISTS FOR A REASON
    ------------------------------
    Every entity annex ends with a "discretionary matters"
    section, so that clause is retrieved for almost any
    question about that annex. Treating its mere presence as
    decisive sends straightforward entitlement questions to a
    human: "how much parental leave do I get" matched A3.1 at
    0.875 and was handed off because A5 sat at 0.675 further
    down the same list.

    So it has to beat the field, not merely appear in it. A
    discretionary clause decides only when nothing else is
    clearly answering better - which is exactly when the
    question really is about the discretionary case.
    """

    if not results:
        return None

    best = results[0].get("score", 0.0)

    for result in results:

        if not DISCRETIONARY.search(
            result.get("text", "")
        ):
            continue

        if (
            best - result.get("score", 0.0)
            <= DISCRETION_MARGIN
        ):
            return citation_of(result)

    return None


def answer_policy_question(
    question: str,
    employee_id: str,
    retriever,
    records,
    generator=None,
    today: date | None = None,
    labels: dict | None = None,
    log_path: str | None = None,
) -> DeskAnswer:
    """
    One policy question, end to end.

    `records(employee_id) -> dict` is injected rather than
    imported so the desk can run against the local fixture or
    against the HRIS tool over MCP without knowing which.
    """

    prompt_version = getattr(
        generator,
        "prompt_version",
        CURRENT_PROMPT_VERSION,
    )

    recorder_kwargs = {
        "question": question,
        "prompt_version": prompt_version,
        "labels": {
            # The employee id is an identifier, not a
            # protected attribute, so it is logged. Grade,
            # entity and leave balance are not - see
            # app/desk/redaction.py.
            "employee_id": employee_id,
            **(labels or {}),
        },
    }

    if log_path is not None:
        recorder_kwargs["path"] = log_path

    with Recorder(**recorder_kwargs) as trace:

        # ---- 1. who is asking -------------------------
        with trace.span(
            "resolve_subject",
            "tools",
            tool="get_employee_record",
        ) as span:

            record = records(employee_id)

            if record is None or "error" in record:

                trace.answer = (
                    "I could not read your employee "
                    "record, so I cannot tell which "
                    "entity or grade applies to you. "
                    "Please contact an HR business "
                    "partner."
                )

                trace.abstained = True

                span.attributes["resolved"] = False

                return DeskAnswer(
                    status="handoff",
                    answer=trace.answer,
                    trace_id=trace.trace_id,
                    handoff={
                        "reason": "no_employee_record",
                        "employee_id": employee_id,
                    },
                )

            subject = resolve_subject(
                employee_id,
                record,
                question,
                today,
            )

            # Grade and entity are the answer-deciding facts.
            # They are recorded as resolved/not, never as
            # values - the log is read by the whole squad.
            span.attributes["entity_resolved"] = True

            span.attributes["grade_resolved"] = True

            span.attributes["as_of"] = (
                subject.as_of.isoformat()
            )

        # ---- 2. is this about someone else? -----------
        if asks_about_someone_else(
            question,
            employee_id,
        ):

            # Phrased so it reveals nothing: not whether the
            # colleague exists, not their grade, not their
            # entity. A refusal that says "I cannot tell you
            # about a Grade 6" has already leaked the grade.
            trace.answer = (
                "I can only answer questions about "
                "your own entitlements. For anything "
                "concerning another employee, please "
                "speak to an HR business partner."
            )

            trace.abstained = True

            trace.labels["refusal"] = "third_party"

            return DeskAnswer(
                status="refused",
                answer=trace.answer,
                subject=subject.as_dict(),
                trace_id=trace.trace_id,
            )

        # ---- 3. retrieve, filtered --------------------
        with trace.span(
            "retrieve",
            "retrieval",
            top_k=TOP_K,
            entity=subject.entity,
            as_of=subject.as_of.isoformat(),
        ) as span:

            # Over-fetch, because the edition window cannot
            # be expressed as a Chroma filter and is applied
            # below. Without this the superseded edition's
            # near-duplicates consume the whole top_k - the
            # same clause scores ~0.74 in both editions - and
            # a clause that matters, such as the annex's
            # discretionary section, never survives to be
            # read. An integration bug: neither the filter nor
            # the retriever is wrong alone.
            raw = retriever.retrieve(
                question,
                top_k=TOP_K * OVERFETCH,
                where=policy_filter(subject),
            )

            # Entity was enforced in the query; the edition
            # window is enforced here.
            in_force_results = filter_in_force(
                raw,
                subject,
            )

            ranked = annex_wins(
                in_force_results,
                subject,
            )[:TOP_K]

            span.attributes["returned"] = len(raw)

            span.attributes["in_force"] = len(
                in_force_results
            )

            span.attributes["dropped_superseded"] = (
                len(raw) - len(in_force_results)
            )

            span.attributes["top_score"] = (
                round(ranked[0]["score"], 4)
                if ranked
                else 0.0
            )

        trace.context_ids = [
            result["chunk_id"]
            for result in ranked
        ]

        trace.labels["context"] = [
            {
                "rank": index,
                "chunk_id": result["chunk_id"],
                "policy_id": result[
                    "metadata"
                ].get("policy_id"),
                "section": result[
                    "metadata"
                ].get("section"),
                "version": result[
                    "metadata"
                ].get("version"),
                "effective_date": result[
                    "metadata"
                ].get("effective_date"),
                "entity": result["metadata"].get(
                    "entity"
                ),
                "score": round(
                    result["score"],
                    4,
                ),
                "text": result["text"][:600],
            }
            for index, result in enumerate(
                ranked,
                start=1,
            )
        ]

        # ---- 4. nothing relevant ----------------------
        if (
            not ranked
            or ranked[0]["score"] < MIN_SCORE
        ):

            trace.answer = (
                "I could not find a policy covering "
                "that. Please ask an HR business "
                "partner."
            )

            trace.abstained = True

            trace.labels["refusal"] = "out_of_scope"

            return DeskAnswer(
                status="refused",
                answer=trace.answer,
                subject=subject.as_dict(),
                trace_id=trace.trace_id,
            )

        # ---- 5. discretionary -> a human --------------
        # Scanned across everything retrieved, not just the
        # top few. A discretionary clause is decisive wherever
        # it ranks: "extensions are discretionary" answers the
        # question even when the clause stating the standard
        # entitlement matches the words better.
        discretionary = is_discretionary(ranked)

        if discretionary:

            trace.answer = (
                "This is a discretionary matter under "
                f"{format_citation(discretionary)}, "
                "which says it must be decided by an "
                "HR business partner rather than from "
                "the policy alone. I have not guessed "
                "an answer."
            )

            trace.abstained = True

            trace.sources = [discretionary]

            trace.labels["refusal"] = (
                "discretionary"
            )

            return DeskAnswer(
                status="handoff",
                answer=trace.answer,
                citations=[discretionary],
                subject=subject.as_dict(),
                retrieved=trace.labels["context"],
                trace_id=trace.trace_id,
                handoff={
                    "reason": "discretionary",
                    "clause": format_citation(
                        discretionary
                    ),
                },
            )

        # ---- 6. answer --------------------------------
        citations = [
            citation_of(result)
            for result in ranked[:3]
        ]

        with trace.span(
            "generate",
            "generation",
            model=trace.model,
            prompt_version=prompt_version,
        ) as span:

            if generator is None:

                # No model: the clause is returned verbatim
                # with its citation. Less fluent, equally
                # correct, and it keeps the desk demonstrable
                # on an unfunded key.
                answer = _extractive_answer(
                    ranked[0],
                    subject,
                )

                span.attributes["mode"] = (
                    "extractive"
                )

            else:

                generated = generator.generate(
                    question=_grounded_question(
                        question,
                        subject,
                    ),
                    results=ranked[:3],
                )

                meta = generated.pop("_meta", {})

                answer = generated.get(
                    "answer",
                    "",
                )

                span.input_tokens = meta.get(
                    "input_tokens",
                    0,
                )

                span.output_tokens = meta.get(
                    "output_tokens",
                    0,
                )

                span.attributes["mode"] = "model"

        trace.answer = answer

        trace.sources = citations

        return DeskAnswer(
            status="answered",
            answer=answer,
            citations=citations,
            subject=subject.as_dict(),
            retrieved=trace.labels["context"],
            trace_id=trace.trace_id,
        )


def _grounded_question(
    question: str,
    subject: Subject,
) -> str:
    """
    The question, with the resolved facts attached.

    The model is told the grade and entity rather than left to
    infer them, because inference is where a Grade 3 in India
    gets a Grade 6 UK answer.
    """

    return (
        f"{question}\n\n"
        f"[Resolved from the employee record: "
        f"entity {subject.entity}, grade "
        f"{subject.grade} ({subject.band}), "
        f"answer must be correct as of "
        f"{subject.as_of.isoformat()}.]"
    )


def _extractive_answer(
    result: dict,
    subject: Subject,
) -> str:

    citation = citation_of(result)

    text = result["text"].strip()

    # The heading is already the first line of the chunk.
    body = "\n".join(text.split("\n")[1:]).strip()

    return (
        f"{body[:600]}\n\n"
        f"-- {format_citation(citation)}, which "
        f"applies to you as {subject.band} in the "
        f"{subject.entity} entity."
    )
