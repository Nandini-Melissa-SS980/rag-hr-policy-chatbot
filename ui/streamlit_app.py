"""
HR Policy Chatbot - Streamlit UI.

Run from the repository root:

    streamlit run ui/streamlit_app.py

Shows the answer beside the chunks it came from, so
retrieval can be inspected rather than guessed at.
Generation is optional: if the model is unavailable
the retrieval side still works, because embeddings
run locally.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Streamlit puts this file's own directory first on
# sys.path, so the repository root is forced ahead
# of it - otherwise `import app` could resolve to a
# module in ui/ instead of the app package.
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))

sys.path.insert(0, str(ROOT))

import streamlit as st

from app.services.retriever import Retriever


# A chunk this short is a bare section heading and
# carries no information. Week 5 found these in the
# top 3 of 14 of 20 traces.
EMPTY_CHUNK_CHARS = 60

REFUSAL = (
    "I couldn't find information about this in "
    "the provided HR policy documents."
)

STRATEGIES = {
    "structure_aware": "Structure aware (65 chunks)",
    "basic": "Basic 1000-char windows (30 chunks)",
}


st.set_page_config(
    page_title="HR Policy Chatbot",
    page_icon="📘",
    layout="wide",
)


st.markdown(
    """
    <style>
      .block-container { padding-top: 2.2rem; }

      .card {
        border: 1px solid rgba(128,128,128,.25);
        border-radius: 8px;
        padding: .55rem .7rem;
        margin-bottom: .45rem;
      }
      .card.cited { border-color: rgba(56,142,60,.7); }
      .card.empty { border-color: rgba(214,140,0,.7); }

      .row {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: .5rem;
        font-size: .78rem;
      }
      .ref {
        font-family: ui-monospace, monospace;
        font-weight: 600;
      }
      .score {
        font-family: ui-monospace, monospace;
        opacity: .75;
      }
      .bar {
        height: 3px;
        background: rgba(128,128,128,.2);
        border-radius: 2px;
        margin: .4rem 0 .35rem;
      }
      .fill { height: 3px; border-radius: 2px; }
      .snippet { font-size: .78rem; opacity: .8; line-height: 1.35; }
      .tag {
        font-size: .68rem;
        text-transform: uppercase;
        letter-spacing: .04em;
        padding: .05rem .35rem;
        border-radius: 4px;
        margin-left: .3rem;
      }
      .tag.cited { background: rgba(56,142,60,.18); color: #2e7d32; }
      .tag.empty { background: rgba(214,140,0,.18); color: #b26a00; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def get_retriever(
    strategy: str,
    rerank: bool,
) -> Retriever:
    """
    Cached so the embedding model - and the
    cross-encoder, when reranking - loads once
    rather than on every interaction.
    """

    return Retriever(
        strategy,
        rerank=rerank,
    )


@st.cache_resource(show_spinner=False)
def get_generator():
    """
    Returns the generator, or None with the reason
    it is unavailable.
    """

    try:

        from app.services.generator import (
            Generator,
        )

        return Generator(), None

    except Exception as error:

        return None, (
            f"{type(error).__name__}: {error}"
        )


@st.cache_data(show_spinner=False)
def index_facts(strategy: str) -> dict:

    store = get_retriever(
        strategy,
        False,
    ).vector_store

    metadata = store.all_metadata()

    return {
        "chunks": store.count(),
        "policies": sorted(
            {
                item.get("policy_id", "")
                for item in metadata
            }
        ),
        "regions": sorted(
            {
                item.get("region", "unknown")
                for item in metadata
            }
        ),
    }


def score_colour(score: float) -> str:

    if score >= 0.75:
        return "#2e7d32"

    if score >= 0.60:
        return "#f9a825"

    return "#c62828"


def render_chunk(
    item: dict,
    cited: set[str],
):

    metadata = item["metadata"]

    chunk_id = metadata.get("chunk_id", "")

    text = item["text"].strip()

    is_cited = chunk_id in cited

    is_empty = len(text) < EMPTY_CHUNK_CHARS

    classes = "card"

    if is_cited:
        classes += " cited"
    elif is_empty:
        classes += " empty"

    tags = ""

    if is_cited:
        tags += '<span class="tag cited">cited</span>'

    if is_empty:
        tags += '<span class="tag empty">no content</span>'

    reference = (
        f"{metadata.get('policy_id', '?')} "
        f"§{metadata.get('section', '?')}"
    )

    snippet = " ".join(text.split())[:180]

    # The bar always tracks cosine, which is bounded
    # 0-1. A rerank score is an unbounded logit, so
    # it is shown as a figure only - but it is what
    # the ordering follows, and hiding it makes the
    # cosine column look out of order.
    width = int(
        max(
            0.0,
            min(1.0, item["score"]),
        )
        * 100
    )

    if "rerank_score" in item:

        readout = (
            f"rr {item['rerank_score']:+.2f}"
            f" · cos {item['score']:.3f}"
        )

    else:
        readout = f"{item['score']:.3f}"

    st.markdown(
        f"""
        <div class="{classes}">
          <div class="row">
            <span><span class="ref">{reference}</span>{tags}</span>
            <span class="score">{readout}</span>
          </div>
          <div class="bar">
            <div class="fill" style="width:{width}%;
                 background:{score_colour(item['score'])}"></div>
          </div>
          <div class="snippet">{snippet}…</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def ask(
    question: str,
    strategy: str,
    top_k: int,
    rerank: bool,
    threshold: float,
    region: str | None,
    generate: bool,
) -> dict:

    retriever = get_retriever(
        strategy,
        rerank,
    )

    results = retriever.retrieve(
        question,
        top_k=top_k,
        region=region,
    )

    abstained = not Retriever.has_good_match(
        results,
        threshold=threshold,
    )

    turn = {
        "question": question,
        "results": results,
        "abstained": abstained,
        "answer": None,
        "sources": [],
        "error": None,
    }

    if not results:

        turn["answer"] = REFUSAL

        turn["error"] = (
            "No chunks matched. If a region "
            "filter is set, note that every "
            "chunk is stored as 'unknown'."
        )

        return turn

    if abstained:

        turn["answer"] = REFUSAL

        return turn

    if not generate:
        return turn

    generator, error = get_generator()

    if generator is None:

        turn["error"] = error

        return turn

    try:

        generated = generator.generate(
            question=question,
            results=results,
        )

        turn["answer"] = generated.get(
            "answer",
            "",
        )

        turn["sources"] = generated.get(
            "sources",
            [],
        )

    except Exception as failure:

        turn["error"] = (
            f"{type(failure).__name__}: {failure}"
        )

    return turn


# ---------------------------------------------
# Sidebar
# ---------------------------------------------

if "turns" not in st.session_state:
    st.session_state.turns = []


with st.sidebar:

    st.subheader("Retrieval")

    strategy = st.selectbox(
        "Chunking strategy",
        options=list(STRATEGIES),
        format_func=lambda key: STRATEGIES[key],
    )

    top_k = st.slider(
        "Chunks retrieved (top_k)",
        min_value=1,
        max_value=10,
        value=3,
    )

    rerank = st.toggle(
        "Cross-encoder reranking",
        value=False,
        help=(
            "Re-orders a wider pool with "
            "BAAI/bge-reranker-base. First use "
            "downloads ~1.1GB."
        ),
    )

    threshold = st.slider(
        "Refuse below score",
        min_value=0.0,
        max_value=1.0,
        value=0.45,
        step=0.01,
        help=(
            "The abstention gate. Week 5 found "
            "the lowest real top-1 score was "
            "0.586, so at 0.45 it never fires."
        ),
    )

    facts = index_facts(strategy)

    region = st.selectbox(
        "Region filter",
        options=["all"] + facts["regions"],
    )

    generate = st.toggle(
        "Generate an answer",
        value=True,
        help=(
            "Turn off to inspect retrieval only, "
            "which needs no LLM."
        ),
    )

    st.divider()

    st.caption(
        f"**{facts['chunks']}** chunks · "
        f"{len(facts['policies'])} policies"
    )

    st.caption(
        " · ".join(facts["policies"])
    )

    generator, generator_error = get_generator()

    # A generator that builds is not a generator
    # that answers: the API key can be present and
    # still be out of credit. Report the last real
    # call, not the constructor.
    last_error = next(
        (
            turn["error"]
            for turn in reversed(
                st.session_state.turns
            )
            if turn["error"]
        ),
        None,
    )

    if generator_error:
        st.warning(
            "Generator unavailable — retrieval "
            "still works.",
            icon="⚠️",
        )
    elif last_error:
        st.error(
            "Last generation failed. Turn off "
            "*Generate an answer* to use "
            "retrieval only.",
            icon="🚫",
        )
    else:
        st.info(
            "Generator configured — not yet "
            "called",
            icon="🔌",
        )

    if st.button(
        "Clear conversation",
        use_container_width=True,
    ):
        st.session_state.turns = []
        st.rerun()


# ---------------------------------------------
# Main
# ---------------------------------------------

st.title("HR Policy Chatbot")

st.caption(
    "Answers come only from the indexed HR "
    "policies, with the retrieved chunks shown "
    "alongside."
)

conversation, retrieval = st.columns(
    [3, 2],
    gap="large",
)

with conversation:

    if not st.session_state.turns:

        st.info(
            "Ask something like *How many days of "
            "annual leave do I get?* or *Can I "
            "work from home?*",
            icon="💬",
        )

    for turn in st.session_state.turns:

        with st.chat_message("user"):
            st.write(turn["question"])

        with st.chat_message("assistant"):

            if turn["answer"]:
                st.write(turn["answer"])

            if turn["error"]:
                st.error(
                    turn["error"],
                    icon="🚫",
                )

            if turn["abstained"]:
                st.caption(
                    "Refused: the top score was "
                    "below the threshold."
                )

            if turn["sources"]:

                cited = ", ".join(
                    f"{source.get('policy_id')} "
                    f"§{source.get('section')}"
                    for source in turn["sources"]
                )

                st.caption(f"Sources: {cited}")

with retrieval:

    st.markdown("##### Retrieved chunks")

    if not st.session_state.turns:

        st.caption(
            "The chunks behind the latest answer "
            "appear here, with their cosine "
            "scores."
        )

    else:

        latest = st.session_state.turns[-1]

        cited = {
            source.get("chunk_id")
            for source in latest["sources"]
        }

        st.caption(
            f"`{strategy}` · top {top_k}"
            + (" · reranked" if rerank else "")
        )

        for item in latest["results"]:
            render_chunk(item, cited)

        if not latest["results"]:
            st.caption("Nothing matched.")

        with st.expander("Full chunk text"):

            for item in latest["results"]:

                metadata = item["metadata"]

                st.markdown(
                    f"**{metadata.get('policy_id')} "
                    f"§{metadata.get('section')}** · "
                    f"{metadata.get('source_file')} "
                    f"p{metadata.get('page_number')}"
                )

                st.text(item["text"])


question = st.chat_input(
    "Ask about an HR policy…"
)

if question:

    with st.spinner("Searching policies…"):

        turn = ask(
            question,
            strategy,
            top_k,
            rerank,
            threshold,
            None if region == "all" else region,
            generate,
        )

    st.session_state.turns.append(turn)

    st.rerun()
