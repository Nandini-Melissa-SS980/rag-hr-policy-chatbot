"""
The System endpoint.

It exists so the UI never hardcodes a spec sheet that drifts
from the running code. These pin that: every value must come
from the module that governs the behaviour, and no credential
may ever be returned.
"""


def test_no_credential_is_ever_returned():
    """
    The page reports whether a key is configured. A page that
    renders the key is a page that leaks it to anyone with a
    browser.
    """

    import json

    from app.api.system import system_info

    payload = json.dumps(system_info())

    # The real keys, from the real config.
    from app import config

    for secret in (
        config.OPENAI_API_KEY,
        config.GEMINI_API_KEY,
    ):
        if secret:
            assert secret not in payload


def test_key_state_says_configured_not_the_key():

    from app.api.system import key_state

    assert key_state("sk-abc123") == "configured"
    assert key_state(None) == "not set"
    assert key_state("") == "not set"


def test_the_provider_matches_config():
    """
    Read from config, not written down twice.
    """

    from app import config
    from app.api.system import system_info

    info = system_info()

    assert (
        info["model"]["provider"]
        == config.LLM_PROVIDER
    )

    expected = (
        config.GEMINI_MODEL
        if config.LLM_PROVIDER == "gemini"
        else config.OPENAI_MODEL
    )

    assert info["model"]["model"] == expected


def test_the_abstain_threshold_matches_the_retriever():
    """
    The number on the page is the number that actually gates
    an answer. Hardcoding 0.45 here would let the two drift
    the moment someone tuned the retriever.
    """

    import inspect

    from app.api.system import system_info
    from app.services.retriever import Retriever

    actual = inspect.signature(
        Retriever.has_good_match
    ).parameters["threshold"].default

    assert (
        system_info()["retrieval"]["abstain_below"]
        == actual
    )


def test_backend_versions_are_the_installed_ones():
    """
    requirements.txt says what was asked for; the
    environment says what is running. The page reports the
    second.
    """

    from importlib.metadata import version

    from app.api.system import system_info

    packages = {
        item["name"]: item["version"]
        for item in system_info()["stack"]["backend"]
    }

    assert packages["fastapi"] == version("fastapi")
    assert packages["chromadb"] == version("chromadb")


def test_every_package_has_a_stated_purpose():
    """
    A version number with no explanation is trivia. The page
    is for someone asking what this is built out of.
    """

    from app.api.system import system_info

    info = system_info()

    for group in ("backend", "frontend"):
        for item in info["stack"][group]:
            assert item["purpose"].strip(), (
                f"{item['name']} has no purpose"
            )


def test_the_three_agent_tools_are_listed():

    from app.agent.tools import TOOLS
    from app.api.system import system_info

    listed = {
        tool["name"]
        for tool in system_info()["agent"]["tools"]
    }

    assert listed == set(TOOLS)
