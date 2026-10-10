import json

from app.agent.loop import Budgets
from app.agent.orchestrator import (
    ELIGIBILITY_TOOLS,
    POLICY_TOOLS,
    Handoff,
    HandoffLog,
    run_orchestrator,
    subset_toolset,
)
from evaluation.week10.judge_offline import (
    OfflineJudge,
)
from evaluation.week10.race_multi import (
    CASE_IDS,
    FAILURE_CASE_ID,
    classify_failure_handling,
    load_cases,
    percentile,
)


def team_stub(
    instructions,
    items,
    tools=None,
    worker="manager",
):
    """
    Answers immediately for every component, so the
    orchestrator's hand-off structure can be checked
    without a model or a plan.
    """

    payload = {
        "answer": f"{worker} says so.",
        "value": None,
        "sources": [
            {
                "policy_id": "HR-202",
                "section": "2.1",
            }
        ],
    }

    text = json.dumps(payload)

    return {
        "tool_calls": [],
        "text": text,
        "input_tokens": 100,
        "output_tokens": 20,
    }


# ---------------- specialists are narrow ----------


def test_each_specialist_holds_a_subset():
    """
    The narrow toolset is the only plausible source
    of a win, so a worker handed the full set would
    delete what the race is testing.
    """

    policy = subset_toolset(POLICY_TOOLS)

    eligibility = subset_toolset(
        ELIGIBILITY_TOOLS
    )

    assert set(policy.functions) == {
        "search_handbook"
    }

    assert set(eligibility.functions) == {
        "get_employee_record",
        "get_jurisdiction_rules",
    }


def test_the_specialists_do_not_overlap():

    policy = set(
        subset_toolset(
            POLICY_TOOLS
        ).functions
    )

    eligibility = set(
        subset_toolset(
            ELIGIBILITY_TOOLS
        ).functions
    )

    assert not (policy & eligibility)


def test_a_narrow_toolset_is_cheaper_to_send():
    """
    The schema discount that explains the sub-1.0
    multiplier. Pinned so the explanation in the
    race table cannot silently stop being true.
    """

    from app.agent.tools import build_toolset

    def tokens(schemas):
        return len(json.dumps(schemas))

    assert tokens(
        subset_toolset(POLICY_TOOLS).schemas
    ) < tokens(build_toolset().schemas)


# ---------------- hand-off accounting -------------


def test_new_tokens_is_total_minus_resent():

    handoff = Handoff(
        index=1,
        sender="manager",
        receiver="policy",
        brief="b",
        input_tokens=900,
        output_tokens=100,
        resent_tokens=400,
    )

    assert handoff.total_tokens == 1000

    assert handoff.new_tokens == 600


def test_resent_never_goes_negative():

    handoff = Handoff(
        index=1,
        sender="manager",
        receiver="policy",
        brief="b",
        input_tokens=10,
        output_tokens=0,
        resent_tokens=999,
    )

    assert handoff.new_tokens == 0


def test_the_log_names_its_largest_handoff():

    log = HandoffLog()

    log.add(
        Handoff(
            1,
            "manager",
            "policy",
            "b",
            input_tokens=100,
            output_tokens=10,
        )
    )

    log.add(
        Handoff(
            2,
            "workers",
            "manager",
            "b",
            input_tokens=900,
            output_tokens=90,
        )
    )

    assert (
        log.largest().receiver == "manager"
    )

    assert log.total_tokens == 1100


def test_every_handoff_is_logged_with_tokens():

    result = run_orchestrator(
        "How many days of annual leave do I get?",
        team_stub,
        Budgets(),
        plan={"use_eligibility": False},
    )

    assert len(result["handoffs"]) == 2

    for handoff in result["handoffs"]:

        assert handoff["total_tokens"] > 0

        assert "sender" in handoff

        assert "receiver" in handoff


def test_eligibility_adds_a_third_handoff():

    result = run_orchestrator(
        "How long must I work here first?",
        team_stub,
        Budgets(),
        plan={"use_eligibility": True},
    )

    receivers = [
        handoff["receiver"]
        for handoff in result["handoffs"]
    ]

    assert receivers == [
        "policy",
        "eligibility",
        "manager",
    ]


# ---------------- the injected failure ------------


def test_a_failed_worker_is_logged_as_failed():

    result = run_orchestrator(
        "How do I book time off?",
        team_stub,
        Budgets(),
        plan={"use_eligibility": False},
        fail_policy_worker=True,
    )

    first = result["handoffs"][0]

    assert first["receiver"] == "policy"

    assert first["status"] == "FAILED"

    assert result["failures"][0][
        "status"
    ] == 500


def test_a_manager_that_cites_after_a_500_is_a_lie():
    """
    The classifier reads the answer, not the design.
    A manager told its worker failed and citing a
    policy anyway has lied, whatever its prompt said.
    """

    behaviour, _ = (
        classify_failure_handling(
            {
                "answer": (
                    "You book time off in the HR "
                    "system."
                ),
                "sources": [
                    {
                        "policy_id": "HR-202",
                        "section": "2.4",
                    }
                ],
                "handoffs": [
                    {
                        "receiver": "policy",
                        "status": "FAILED",
                    }
                ],
            }
        )
    )

    assert behaviour == "lied"


def test_admitting_the_gap_is_degrading():

    behaviour, _ = (
        classify_failure_handling(
            {
                "answer": (
                    "I could not establish this; "
                    "the specialist failed."
                ),
                "sources": [],
                "handoffs": [
                    {
                        "receiver": "policy",
                        "status": "FAILED",
                    }
                ],
            }
        )
    )

    assert behaviour == "degraded"


# ---------------- the ruler does not move ---------


def test_the_race_runs_ten_week6_cases():
    """
    A changed eval set voids the comparison, so the
    ids are pinned and must resolve against the
    Week-6 file.
    """

    assert len(CASE_IDS) == 10

    cases = load_cases()

    assert [
        case["id"] for case in cases
    ] == CASE_IDS


def test_the_ten_cases_span_the_failure_modes():

    modes = {
        case["mode"] for case in load_cases()
    }

    assert len(modes) >= 4


def test_the_failure_case_is_one_of_the_ten():

    assert FAILURE_CASE_ID in CASE_IDS


# ---------------- scoring -------------------------


def test_the_judge_fails_an_invented_citation():

    judge = OfflineJudge(
        {("HR-202", "2.1")}
    )

    verdict = judge.judge(
        "q",
        "an answer",
        [
            {
                "policy_id": "HR-999",
                "section": "9.9",
            }
        ],
    )

    assert verdict["verdict"] == "FAIL"


def test_the_judge_passes_a_real_citation():

    judge = OfflineJudge(
        {("HR-202", "2.1")}
    )

    verdict = judge.judge(
        "q",
        "an answer",
        [
            {
                "policy_id": "HR-202",
                "section": "2.1",
            }
        ],
    )

    assert verdict["verdict"] == "PASS"


def test_an_uncited_answer_fails():

    judge = OfflineJudge({("HR-202", "2.1")})

    assert (
        judge.judge("q", "an answer", [])[
            "verdict"
        ]
        == "FAIL"
    )


def test_percentile_picks_the_slowest_for_p99():

    assert (
        percentile([1.0, 2.0, 9.0], 0.99) == 9.0
    )


def test_percentile_handles_an_empty_list():

    assert percentile([], 0.5) == 0.0
