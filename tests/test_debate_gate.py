# story: e02s01
"""The Debate Gate: an evidence-alignment judge between the analysts and the debate.

The Bull/Bear debate used to run unconditionally after the analyst phase, spending
``2 x max_debate_rounds`` full LLM calls re-arguing evidence the four analysts already
agreed on. The gate judges whether genuine tension exists and routes with a LangGraph
``Command`` either into the debate (Bull Researcher) or straight past it (Research
Manager).

Skipping is the risky direction, so every test here pins the conservative half of the
contract: only clear alignment with adequate confidence skips the debate, and any
failure -- exception, ``None``, unparseable payload, unknown policy -- lands back on
the debate with a warning (never silently, never a fabricated alignment).

Scenario IDs (specs/tech-architecture/e02-TEST_PLAN_LATEST.md):
    # scenario: SC-e02s01-P0-01  gate failure is fail-safe -> debate runs, warning logged
    # scenario: SC-e02s01-P0-02  debate_gate=always -> node sequence == unconditional sequence
    # scenario: SC-e02s01-P0-03  conflicted / low-confidence -> debate runs
    # scenario: SC-e02s01-P0-04  aligned + confident -> skip with an explicit marker
    # scenario: SC-e02s01-P0-05  rating integrity survives a skip (never REVIEW)
    # scenario: SC-e02s01-P1-01  Command goto targets are statically compiled nodes
    # scenario: SC-e02s01-P1-02  unknown mode raises; env override reaches the config
    # scenario: SC-e02s01-P1-03  skipped-debate paragraph only on skip; held text unchanged
    # scenario: SC-e02s01-P1-04  create_initial_state pre-initializes the gate field
    # scenario: SC-e02s01-P1-05  always/never make zero gate LLM calls
    # scenario: SC-e02s01-P2-01  non-English reports gate identically
"""

from __future__ import annotations

import contextlib
import copy
import logging
import typing
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import ValidationError

from tradingagents.agents.gate import create_debate_gate
from tradingagents.agents.managers.research_manager import create_research_manager
from tradingagents.agents.schemas import (
    DebateGateVerdict,
    PortfolioRating,
    ResearchPlan,
    render_debate_gate_marker,
)
from tradingagents.agents.utils.rating import RATING_REVIEW, RATINGS_5_TIER

# ---------------------------------------------------------------------------
# Fakes and helpers
# ---------------------------------------------------------------------------

BULL = "Bull Researcher"
BEAR = "Bear Researcher"
RM = "Research Manager"
GATE = "Debate Gate"

REPORTS = {
    "market_report": "Market: price trending up, volume confirms.",
    "sentiment_report": "Sentiment: news and social both constructive.",
    "news_report": "News: guidance raised, no adverse headlines.",
    "fundamentals_report": "Fundamentals: margins expanding, cash flow strong.",
}


@contextlib.contextmanager
def _policy(mode):
    """Run the gate under one ``debate_gate`` mode without leaking it to other tests.

    The gate reads the mode from the global config at invocation time (house
    pattern, cf. ``get_language_instruction``), so the mode is set through
    ``set_config`` exactly as a real run would, and restored afterwards.
    """
    from tradingagents.dataflows import config as config_module

    previous = config_module._config
    override = copy.deepcopy(previous)
    if mode is None:
        override.pop("debate_gate", None)
    else:
        override["debate_gate"] = mode
    config_module._config = override
    try:
        yield
    finally:
        config_module._config = previous


def _state(**overrides):
    """A bare programmatic state -- the shape a node must survive without the graph."""
    state = {
        "company_of_interest": "NVDA",
        "asset_type": "stock",
        "trade_date": "2026-09-20",
        **REPORTS,
        "investment_debate_state": {
            "bull_history": "",
            "bear_history": "",
            "history": "",
            "current_response": "",
            "judge_decision": "",
            "count": 0,
        },
    }
    state.update(overrides)
    return state


class _StructuredStub:
    """The ``llm.with_structured_output(schema)`` result: a verdict, a raise, or None."""

    def __init__(self, owner, result=None, error=None):
        self._owner = owner
        self._result = result
        self._error = error

    def invoke(self, prompt):
        self._owner.invocations += 1
        self._owner.prompts.append(prompt)
        if self._error is not None:
            raise self._error
        return self._result


class _GateLLM:
    """Fake quick model that counts every invocation and can fail on demand.

    ``invocations`` counts the judge calls the gate actually makes, so the
    ``always`` / ``never`` policy short-circuits can be asserted at zero and a
    free-text retry on the failure path would show up as an extra call.
    """

    def __init__(self, result=None, error=None):
        self.invocations = 0
        self.prompts = []
        self.schema = None
        self._stub = _StructuredStub(self, result=result, error=error)

    def with_structured_output(self, schema, **kwargs):
        self.schema = schema
        return self._stub

    def invoke(self, prompt):
        self.invocations += 1
        self.prompts.append(prompt)
        response = MagicMock()
        response.content = "free-text fallback"
        return response


def _hold_verdict():
    return DebateGateVerdict(
        evidence_aligned=True,
        confidence="high",
        aligned_direction="bullish",
        rationale="All four reports point the same way.",
    )


def _debate_verdict(**overrides):
    fields = {
        "evidence_aligned": False,
        "confidence": "high",
        "aligned_direction": "mixed",
        "rationale": "Sources disagree on the margin trajectory.",
    }
    fields.update(overrides)
    return DebateGateVerdict(**fields)


def _routed(command):
    """The routing decision out of a gate return value (Command or path_map dict)."""
    goto = getattr(command, "goto", None)
    return goto or command["goto"]


def _update(command):
    return getattr(command, "update", None) or command["update"] or {}


def _prompt_text(prompt) -> str:
    """Flatten a captured prompt (str, message list, or objects) to text."""
    if isinstance(prompt, str):
        return prompt
    parts = []
    for m in prompt:
        content = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
        parts.append(str(content))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Schema and marker (SC-e02s01-P0-04, P2-01)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_verdict_schema_defaults_to_no_aligned_direction():
    # scenario: SC-e02s01-P0-03 — nothing to align on, so the judge names no direction.
    verdict = DebateGateVerdict(
        evidence_aligned=False, confidence="low", rationale="Thin evidence."
    )
    assert verdict.aligned_direction is None


@pytest.mark.unit
@pytest.mark.parametrize("confidence", ["low", "medium", "high"])
def test_verdict_confidence_accepts_only_the_three_levels(confidence):
    verdict = DebateGateVerdict(
        evidence_aligned=True,
        confidence=confidence,
        aligned_direction="bullish",
        rationale="r",
    )
    assert verdict.confidence == confidence


@pytest.mark.unit
@pytest.mark.parametrize("confidence", ["very high", "HIGH", "", "certain"])
def test_verdict_rejects_an_unknown_confidence(confidence):
    # Routing keys on confidence == "low", so a surprise value must not be
    # silently coerced into a skip.
    with pytest.raises(ValidationError):
        DebateGateVerdict(
            evidence_aligned=True,
            confidence=confidence,
            aligned_direction="bullish",
            rationale="r",
        )


@pytest.mark.unit
def test_verdict_requires_evidence_aligned_and_rationale():
    with pytest.raises(ValidationError):
        DebateGateVerdict(confidence="high", aligned_direction="bullish", rationale="r")
    with pytest.raises(ValidationError):
        DebateGateVerdict(evidence_aligned=True, confidence="high")


@pytest.mark.unit
@pytest.mark.parametrize("direction", ["bullish", "bearish", "unclear"])
def test_marker_propagates_the_aligned_direction(direction):
    # scenario: SC-e02s01-P2-01
    verdict = DebateGateVerdict(
        evidence_aligned=True,
        confidence="high",
        aligned_direction=direction,
        rationale="r",
    )
    assert direction in render_debate_gate_marker(verdict)


@pytest.mark.unit
def test_marker_is_never_empty_so_a_missing_transcript_cannot_read_as_empty():
    # scenario: SC-e02s01-P0-04 — the RM must never receive an empty debate history.
    marker = render_debate_gate_marker(_hold_verdict())
    assert marker.strip()
    assert "high" in marker
    assert _hold_verdict().rationale in marker


# ---------------------------------------------------------------------------
# Gate routing matrix (SC-e02s01-P0-01/03/04, P1-05, P2-01)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "verdict",
    [
        _debate_verdict(evidence_aligned=False),
        _debate_verdict(evidence_aligned=True, confidence="low", aligned_direction="bullish"),
        _debate_verdict(evidence_aligned=True, confidence="medium", aligned_direction="mixed"),
        _debate_verdict(evidence_aligned=True, confidence="high", aligned_direction="mixed"),
        _debate_verdict(evidence_aligned=True, confidence="high", aligned_direction="unclear"),
        _debate_verdict(evidence_aligned=True, confidence="high", aligned_direction=None),
    ],
    ids=[
        "conflicted",
        "low-confidence",
        "medium-mixed-direction",
        "mixed-direction",
        "unclear-direction",
        "no-direction",
    ],
)
def test_tension_or_ambiguity_routes_to_the_debate(verdict):
    # scenario: SC-e02s01-P0-03 — anything short of clear alignment keeps the debate.
    llm = _GateLLM(result=verdict)
    with _policy("auto"):
        command = create_debate_gate(llm)(_state())
    assert _routed(command) == BULL


@pytest.mark.unit
def test_aligned_and_confident_routes_past_the_debate():
    # scenario: SC-e02s01-P0-04
    llm = _GateLLM(result=_hold_verdict())
    with _policy("auto"):
        command = create_debate_gate(llm)(_state())
    assert _routed(command) == RM
    assert llm.invocations == 1
    history = _update(command)["investment_debate_state"]["history"]
    assert history.strip()
    assert history == render_debate_gate_marker(_hold_verdict())


@pytest.mark.unit
@pytest.mark.parametrize(
    "confidence,direction",
    [
        ("high", "bullish"),
        ("high", "bearish"),
        ("medium", "bullish"),
        ("medium", "bearish"),
    ],
)
def test_aligned_above_low_confidence_with_a_direction_routes_past_the_debate(confidence, direction):
    # scenario: SC-e02s01-P0-04 — the frozen acceptance criterion is
    # `evidence_aligned=true with confidence != "low"` (spec §17). `medium` is
    # above low, so an aligned directional verdict skips the debate.
    verdict = DebateGateVerdict(
        evidence_aligned=True,
        confidence=confidence,
        aligned_direction=direction,
        rationale="All four reports point the same way.",
    )
    llm = _GateLLM(result=verdict)
    with _policy("auto"):
        command = create_debate_gate(llm)(_state())
    assert _routed(command) == RM
    assert _update(command)["investment_debate_state"]["history"] == render_debate_gate_marker(
        verdict
    )


@pytest.mark.unit
def test_unparseable_gate_result_routes_to_the_debate():
    # scenario: SC-e02s01-P0-01
    llm = _GateLLM(result=None)
    with _policy("auto"):
        command = create_debate_gate(llm)(_state())
    assert _routed(command) == BULL
    assert _update(command)["debate_gate_verdict"]


@pytest.mark.unit
def test_gate_exception_is_fail_safe_and_logged(caplog):
    # scenario: SC-e02s01-P0-01
    llm = _GateLLM(error=RuntimeError("provider exploded"))
    with _policy("auto"), caplog.at_level(logging.WARNING):
        command = create_debate_gate(llm)(_state())
    assert _routed(command) == BULL
    assert any(r.levelno >= logging.WARNING for r in caplog.records)
    assert _update(command)["debate_gate_verdict"]


@pytest.mark.unit
def test_a_failed_gate_does_not_retry_as_free_text(caplog):
    # scenario: SC-e02s01-P0-01 — failing safe must not cost an extra LLM call.
    llm = _GateLLM(error=RuntimeError("provider exploded"))
    with _policy("auto"), caplog.at_level(logging.WARNING):
        create_debate_gate(llm)(_state())
    assert llm.invocations == 1


@pytest.mark.unit
def test_never_policy_skips_without_asking_the_judge():
    # scenario: SC-e02s01-P1-05
    llm = _GateLLM(result=_debate_verdict())
    with _policy("never"):
        command = create_debate_gate(llm)(_state())
    assert _routed(command) == RM
    assert llm.invocations == 0
    assert llm.prompts == []


@pytest.mark.unit
def test_always_policy_runs_the_debate_without_asking_the_judge():
    # scenario: SC-e02s01-P1-05
    llm = _GateLLM(result=_hold_verdict())
    with _policy("always"):
        command = create_debate_gate(llm)(_state())
    assert _routed(command) == BULL
    assert llm.invocations == 0
    assert llm.prompts == []


@pytest.mark.unit
def test_missing_policy_falls_back_to_auto():
    llm = _GateLLM(result=_debate_verdict(evidence_aligned=False))
    with _policy(None):
        command = create_debate_gate(llm)(_state())
    assert _routed(command) == BULL


@pytest.mark.unit
def test_unknown_policy_never_skips_the_debate():
    # A mode the graph did not validate must not become an accidental skip.
    llm = _GateLLM(result=_hold_verdict())
    with _policy("sometimes"):
        command = create_debate_gate(llm)(_state())
    assert _routed(command) == BULL


@pytest.mark.unit
def test_the_judge_sees_all_four_reports_and_an_absent_marker():
    # scenario: SC-e02s01-P0-03
    llm = _GateLLM(result=_debate_verdict())
    state = _state(sentiment_report="", company_of_interest="MSFT")
    with _policy("auto"):
        create_debate_gate(llm)(state)
    prompt = _prompt_text(llm.prompts[0])
    assert REPORTS["market_report"] in prompt
    assert REPORTS["news_report"] in prompt
    assert REPORTS["fundamentals_report"] in prompt
    assert "not available" in prompt  # report_or_absent marker for the missing report
    assert "MSFT" in prompt


@pytest.mark.unit
def test_non_english_reports_route_identically():
    # scenario: SC-e02s01-P2-01 — the verdict is language-agnostic; the marker is internal.
    llm = _GateLLM(result=_hold_verdict())
    state = _state(
        market_report="市场：价格上行，成交量确认。",
        sentiment_report="情绪：消息面偏多。",
        fundamentals_report="基本面：利润率扩张。",
    )
    with _policy("auto"):
        command = create_debate_gate(llm)(state)
    assert _routed(command) == RM
    assert _update(command)["investment_debate_state"]["history"] == render_debate_gate_marker(
        _hold_verdict()
    )


@pytest.mark.unit
def test_policy_is_read_at_invocation_not_at_factory_build():
    # House pattern (cf. get_language_instruction): the factory is built once at
    # graph construction; the mode may change before the node runs.
    llm = _GateLLM(result=_hold_verdict())
    node = create_debate_gate(llm)
    with _policy("never"):
        assert _routed(node(_state())) == RM
    with _policy("always"):
        assert _routed(node(_state())) == BULL


# ---------------------------------------------------------------------------
# Initial state (SC-e02s01-P1-04)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_create_initial_state_pre_initializes_the_gate_verdict():
    # scenario: SC-e02s01-P1-04
    from tradingagents.graph.propagation import Propagator

    state = Propagator().create_initial_state("NVDA", "2026-09-20")
    assert state["debate_gate_verdict"] == ""


@pytest.mark.unit
def test_agent_state_declares_the_gate_verdict_field():
    # scenario: SC-e02s01-P1-04
    from tradingagents.agents.utils.agent_states import AgentState

    assert "debate_gate_verdict" in AgentState.__annotations__


# ---------------------------------------------------------------------------
# Graph wiring (SC-e02s01-P1-01)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_graph_compiles_with_the_gate_node_registered():
    # scenario: SC-e02s01-P1-01 — every Command goto target is a compiled node, so a
    # drifted label cannot crash LangGraph mid-run (#1088 class).
    graph, _llm = _compiled_graph("auto")
    nodes = set(graph.get_graph().nodes)
    assert GATE in nodes
    assert {BULL, BEAR, RM} <= nodes


@pytest.mark.unit
def test_gate_command_targets_are_registered_graph_nodes():
    # scenario: SC-e02s01-P1-01
    graph, _llm = _compiled_graph("auto")
    nodes = set(graph.get_graph().nodes)
    held = _GateLLM(result=_debate_verdict())
    with _policy("auto"):
        held_target = _routed(create_debate_gate(held)(_state()))
    skip = _GateLLM(result=_hold_verdict())
    with _policy("auto"):
        skip_target = _routed(create_debate_gate(skip)(_state()))
    assert {held_target, skip_target} <= nodes
    assert held_target != skip_target


@pytest.mark.unit
def test_gate_declares_its_targets_as_a_literal_union():
    # scenario: SC-e02s01-P1-01 — the type annotation is the static guard.
    hints = typing.get_type_hints(create_debate_gate)
    command_args = typing.get_args(hints["return"])
    assert command_args, "create_debate_gate must be annotated -> Command[Literal[...]]"
    assert set(typing.get_args(command_args[0])) == {BULL, RM}


# ---------------------------------------------------------------------------
# Research Manager prompt variants (SC-e02s01-P0-05, P1-03)
# ---------------------------------------------------------------------------


def _rm_llm(captured: dict):
    """Research Manager LLM whose structured binding records the prompt it was handed."""
    structured = MagicMock()

    def _invoke(prompt):
        captured["prompt"] = prompt
        return ResearchPlan(
            recommendation=PortfolioRating.BUY,
            rationale="Aligned reports carry the call.",
            strategic_actions="Build in thirds.",
        )

    structured.invoke.side_effect = _invoke
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    return llm


def _held_state():
    return _state(
        debate_gate_verdict="",
        investment_debate_state={
            "bull_history": "Bull Analyst: growth is intact.",
            "bear_history": "Bear Analyst: margins are at risk.",
            "history": "Bull Analyst: growth is intact.\nBear Analyst: margins are at risk.",
            "current_response": "Bear Analyst: margins are at risk.",
            "judge_decision": "",
            "count": 2,
        },
    )


def _skipped_state():
    marker = render_debate_gate_marker(_hold_verdict())
    return _state(
        debate_gate_verdict=marker,
        investment_debate_state={
            "bull_history": "",
            "bear_history": "",
            "history": marker,
            "current_response": "",
            "judge_decision": "",
            "count": 0,
        },
    )


@pytest.mark.unit
def test_research_manager_skipped_debate_prompt_states_uncontested_evidence():
    # scenario: SC-e02s01-P1-03 — a skip has no conflict to weigh, so the prompt that
    # asserts conflict is replaced, not merely softened.
    captured = {}
    create_research_manager(_rm_llm(captured))(_skipped_state())
    text = _prompt_text(captured["prompt"])
    assert "uncontested" in text.lower()
    assert "The debate always contains conflicting arguments" not in text


@pytest.mark.unit
def test_research_manager_held_debate_prompt_is_unchanged():
    # scenario: SC-e02s01-P1-03 — the held path keeps today's text byte for byte.
    captured = {}
    create_research_manager(_rm_llm(captured))(_held_state())
    text = _prompt_text(captured["prompt"])
    assert "The debate always contains conflicting arguments" in text
    assert "uncontested" not in text.lower()
    assert "Bull Analyst: growth is intact." in text


@pytest.mark.unit
def test_research_manager_skip_path_still_yields_a_five_tier_rating():
    # scenario: SC-e02s01-P0-05 — the skip must not drift into REVIEW (#1170).
    from tradingagents.graph.signal_processing import SignalProcessor

    captured = {}
    plan = create_research_manager(_rm_llm(captured))(_skipped_state())["investment_plan"]
    signal = SignalProcessor().process_signal(plan)
    assert signal in RATINGS_5_TIER
    assert signal != RATING_REVIEW


@pytest.mark.unit
def test_research_manager_skip_path_prompt_tells_the_model_what_to_do():
    # scenario: SC-e02s01-P0-04 — #1176 fabrication class: an empty transcript must not
    # read as "the debate was held and found nothing".
    captured = {}
    create_research_manager(_rm_llm(captured))(_skipped_state())
    text = _prompt_text(captured["prompt"]).lower()
    assert "aligned" in text
    assert "do not" in text or "never" in text


# ---------------------------------------------------------------------------
# Config surface (SC-e02s01-P1-02)
# ---------------------------------------------------------------------------


def _reload_default_config(monkeypatch, **overrides):
    import importlib

    import tradingagents.default_config as default_config_module

    for key in list(default_config_module._ENV_OVERRIDES):
        monkeypatch.delenv(key, raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    return importlib.reload(default_config_module)


@pytest.mark.unit
def test_default_config_ships_debate_gate_auto(monkeypatch):
    # scenario: SC-e02s01-P1-02
    module = _reload_default_config(monkeypatch)
    assert module.DEFAULT_CONFIG["debate_gate"] == "auto"


@pytest.mark.unit
def test_the_two_valid_mode_lists_stay_in_sync():
    # default_config cannot import the gate package (circular import at build
    # time), so it carries a copy of the valid set; this guards the copy.
    import tradingagents.default_config as default_config_module
    from tradingagents.agents.gate.debate_gate import DEBATE_GATE_MODES

    assert default_config_module._DEBATE_GATE_MODES == DEBATE_GATE_MODES


@pytest.mark.unit
@pytest.mark.parametrize("mode", ["always", "auto", "never"])
def test_debate_gate_config_is_env_overridable(monkeypatch, mode):
    # scenario: SC-e02s01-P1-02
    module = _reload_default_config(monkeypatch, TRADINGAGENTS_DEBATE_GATE=mode)
    assert module.DEFAULT_CONFIG["debate_gate"] == mode


@pytest.mark.unit
def test_debate_gate_config_rejects_a_bogus_env_value(monkeypatch):
    # scenario: SC-e02s01-P1-02
    with pytest.raises(ValueError) as excinfo:
        _reload_default_config(monkeypatch, TRADINGAGENTS_DEBATE_GATE="bogus")
    message = str(excinfo.value)
    assert "always" in message and "auto" in message and "never" in message


@pytest.mark.unit
def test_config_validation_rejects_a_bogus_mode_at_graph_init(monkeypatch):
    # scenario: SC-e02s01-P1-02 — fail at graph init, before any analyst spend.
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    module = _reload_default_config(monkeypatch)
    config = copy.deepcopy(module.DEFAULT_CONFIG)
    config["debate_gate"] = "bogus"
    with pytest.raises(ValueError) as excinfo:
        TradingAgentsGraph(selected_analysts=("market",), config=config)
    message = str(excinfo.value)
    assert "always" in message and "auto" in message and "never" in message


# ---------------------------------------------------------------------------
# Graph-level end to end (SC-e02s01-P0-01/02/04/05)
# ---------------------------------------------------------------------------


def _compiled_graph(mode: str, verdict: DebateGateVerdict | None = None, error=None):
    """Compile the real GraphSetup graph with every agent factory stubbed.

    The gate is the real factory and its judge LLM is a call-counting fake:
    SC-e02s01-P0-02 asserts zero judge calls, which a stubbed gate would make vacuous.
    """
    from tradingagents.graph.conditional_logic import ConditionalLogic
    from tradingagents.graph.setup import GraphSetup

    llm = _GateLLM(result=verdict, error=error)

    def _noop(
        name, extra=None, writes_message=False, advances_debate=False, advances_risk=False
    ):
        def _node(state):
            update = dict(extra or {})
            if writes_message:
                # The analyst routers read the last message; a stub that writes
                # none makes the real ConditionalLogic blow up on the empty list.
                update["messages"] = [AIMessage(content=name, tool_calls=[])]
            if advances_debate:
                # The debate loop terminates on investment_debate_state.count, so a
                # stub debater that writes nothing loops until the recursion limit.
                count = state["investment_debate_state"]["count"] + 1
                update["investment_debate_state"] = {
                    **state["investment_debate_state"],
                    "count": count,
                    "current_response": f"{name}: argument {count}",
                    "history": f"{name}: argument {count}",
                }
            if advances_risk:
                count = state["risk_debate_state"]["count"] + 1
                update["risk_debate_state"] = {
                    **state["risk_debate_state"],
                    "count": count,
                    "latest_speaker": name,
                    "history": f"{name}: risk argument {count}",
                }
            return update
        _node.__name__ = name
        return _node

    tool_nodes = {key: MagicMock() for key in ("market", "social", "news", "fundamentals")}
    with contextlib.ExitStack() as stack:
        for target, factory in (
            # Analysts are stubbed too: the real factories bind tools to a chat
            # model, and this run must stay offline with fake LLMs.
            (
                "create_market_analyst",
                lambda _llm: _noop("Market Analyst", REPORTS, writes_message=True),
            ),
            (
                "create_sentiment_analyst",
                lambda _llm: _noop("Sentiment Analyst", REPORTS, writes_message=True),
            ),
            (
                "create_news_analyst",
                lambda _llm: _noop("News Analyst", REPORTS, writes_message=True),
            ),
            (
                "create_fundamentals_analyst",
                lambda _llm: _noop("Fundamentals Analyst", REPORTS, writes_message=True),
            ),
            ("create_bull_researcher", lambda _llm: _noop(BULL, advances_debate=True)),
            ("create_bear_researcher", lambda _llm: _noop(BEAR, advances_debate=True)),
            ("create_research_manager", _research_manager_stub),
            ("create_trader", lambda _llm: _noop("Trader")),
            (
                "create_aggressive_debator",
                lambda _llm: _noop("Aggressive Analyst", advances_risk=True),
            ),
            (
                "create_conservative_debator",
                lambda _llm: _noop("Conservative Analyst", advances_risk=True),
            ),
            ("create_neutral_debator", lambda _llm: _noop("Neutral Analyst", advances_risk=True)),
            ("create_portfolio_manager", lambda _llm: _noop("Portfolio Manager")),
        ):
            stack.enter_context(patch(f"tradingagents.graph.setup.{target}", factory))
        setup = GraphSetup(llm, llm, tool_nodes, ConditionalLogic(1, 1))
        with _policy(mode):
            workflow = setup.setup_graph(("market",))
    with _policy(mode):
        graph = workflow.compile()
    return graph, llm


def _research_manager_stub(_llm):
    """RM stub that proves the gate's verdict reached it (SC-e02s01-P0-04)."""

    def _node(state):
        verdict = state.get("debate_gate_verdict", "")
        return {
            "investment_plan": (
                "**Recommendation**: Buy\n\n" f"**Rationale**: {verdict or 'debate held'}\n\n"
                "**Strategic Actions**: build in thirds."
            )
        }

    _node.__name__ = RM
    return _node


def _run(graph):
    """Stream one run; return (visited node order, final state)."""
    initial = {
        "messages": [HumanMessage(content="analyse NVDA")],
        "company_of_interest": "NVDA",
        "asset_type": "stock",
        "trade_date": "2026-09-20",
        "instrument_context": "NVDA (stock)",
        **REPORTS,
        "investment_debate_state": {
            "bull_history": "",
            "bear_history": "",
            "history": "",
            "current_response": "",
            "judge_decision": "",
            "count": 0,
        },
        "risk_debate_state": {
            "aggressive_history": "",
            "conservative_history": "",
            "neutral_history": "",
            "history": "",
            "latest_speaker": "",
            "current_aggressive_response": "",
            "current_conservative_response": "",
            "current_neutral_response": "",
            "judge_decision": "",
            "count": 0,
        },
    }
    visited: list[str] = []
    final = initial
    for kind, payload in graph.stream(
        initial, {"recursion_limit": 50}, stream_mode=["updates", "values"]
    ):
        if kind == "updates":
            visited.extend(payload)
        else:
            final = payload
    return visited, final


@pytest.mark.integration
def test_node_sequence_with_always_matches_the_unconditional_debate():
    # scenario: SC-e02s01-P0-02 — `always` restores exact prior behavior and the gate
    # spends nothing; the sequence is the one main produced before this story.
    graph, llm = _compiled_graph("always")
    with _policy("always"):
        visited, _final = _run(graph)
    assert GATE in visited
    for node in (
        "Market Analyst",
        "Msg Clear Market",
        BULL,
        BEAR,
        RM,
        "Trader",
        "Aggressive Analyst",
        "Conservative Analyst",
        "Neutral Analyst",
        "Portfolio Manager",
    ):
        assert node in visited, f"{node} missing from {visited}"
    assert visited.index(BULL) < visited.index(BEAR) < visited.index(RM)
    assert llm.prompts == []  # zero judge calls


@pytest.mark.integration
def test_node_sequence_skip_never_invokes_the_debaters():
    # scenario: SC-e02s01-P0-04
    graph, _llm = _compiled_graph("auto", verdict=_hold_verdict())
    with _policy("auto"):
        visited, final = _run(graph)
    assert BULL not in visited
    assert BEAR not in visited
    assert visited.index(GATE) < visited.index(RM)
    history = final["investment_debate_state"]["history"]
    assert history.strip()
    assert "aligned" in history.lower()
    assert final["debate_gate_verdict"].strip()


@pytest.mark.integration
def test_skip_path_process_signal_is_a_five_tier_rating():
    # scenario: SC-e02s01-P0-05 — end to end: skip -> RM output -> graph signal.
    from tradingagents.graph.signal_processing import SignalProcessor

    graph, _llm = _compiled_graph("auto", verdict=_hold_verdict())
    with _policy("auto"):
        _visited, final = _run(graph)
    signal = SignalProcessor().process_signal(final["investment_plan"])
    assert signal in RATINGS_5_TIER
    assert signal != RATING_REVIEW


@pytest.mark.integration
def test_gate_failure_end_to_end_falls_back_to_the_debate():
    # scenario: SC-e02s01-P0-01 — a broken judge degrades to today's behavior, not a skip.
    graph, _llm = _compiled_graph("auto", error=RuntimeError("judge unavailable"))
    with _policy("auto"):
        visited, _final = _run(graph)
    assert BULL in visited
    assert BEAR in visited
