"""
The generator prompt, versioned.

A trace that records which prompt produced an answer
is the difference between "the model must have
changed" and a one-hop diagnosis. Every version that
has ever shipped stays in this file, so a logged
`prompt_version` always resolves to the text that
actually ran.

Bump the version when the text changes. Never edit a
released version in place - a trace from last Tuesday
has to keep meaning what it meant last Tuesday.

  v1  The original prompt. Answers from whatever
      context retrieval supplied, with nothing
      telling the model to check that the context is
      actually about the subject that was asked
      about.

  v2  Adds rule 4, the on-topic rule. The Week-11
      drill found the app quoting a notice period out
      of the annual-leave policy: the corpus has no
      notice-period section at all, the retriever
      returned the closest chunks it had, and nothing
      stopped the model answering from them. See
      evaluation/week11/drill.md.
"""


PROMPT_V1 = """
You are an HR policy assistant.

Your job is to answer questions ONLY using the
provided HR policy context.

Rules:

1. Do not use outside knowledge.
2. Do not invent HR policies.
3. If the context does not contain enough information
   to answer the question, refuse to answer.
4. Every factual claim must have a source citation.
5. Citations must use the provided chunk_id,
   policy_id, and section.
6. Keep the answer concise.
7. Return valid JSON only.

Required JSON format:

{
  "answer": "string",
  "sources": [
    {
      "chunk_id": "string",
      "policy_id": "string",
      "section": "string"
    }
  ]
}
"""


# v2 is v1 plus rule 4. Everything else is byte for
# byte the same, so the before/after is attributable
# to one paragraph rather than to a rewrite.
PROMPT_V2 = """
You are an HR policy assistant.

Your job is to answer questions ONLY using the
provided HR policy context.

Rules:

1. Do not use outside knowledge.
2. Do not invent HR policies.
3. If the context does not contain enough information
   to answer the question, refuse to answer.
4. Check that the retrieved context is about the
   subject the question asks about. The passages you
   are given are the closest ones in the index, which
   is not the same as relevant. If the question asks
   about a topic - notice periods, resignation,
   redundancy, maternity, pensions - and no retrieved
   passage actually covers that topic, refuse. A
   figure lifted from a passage about a different
   subject is a wrong answer even when the figure
   itself is real.
5. Every factual claim must have a source citation.
6. Citations must use the provided chunk_id,
   policy_id, and section.
7. Keep the answer concise.
8. Return valid JSON only.

Required JSON format:

{
  "answer": "string",
  "sources": [
    {
      "chunk_id": "string",
      "policy_id": "string",
      "section": "string"
    }
  ]
}
"""


PROMPTS = {
    "v1": PROMPT_V1,
    "v2": PROMPT_V2,
}


# What ships today. The drill's fix is the bump from
# v1 to v2; evaluation/week11/rollback.md says how to
# put it back and what to watch while it rolls out.
CURRENT_PROMPT_VERSION = "v2"


def get_prompt(
    version: str = CURRENT_PROMPT_VERSION,
) -> str:

    if version not in PROMPTS:

        raise ValueError(
            f"Unknown prompt version: {version}. "
            f"Known: {', '.join(sorted(PROMPTS))}."
        )

    return PROMPTS[version]
