# TradingAgents/agents/gate/debate_gate.py
"""Debate Gate: route an evidence-aligned run past the Bull/Bear debate.

The debate used to run unconditionally after the analyst phase, spending
``2 x max_debate_rounds`` full LLM calls re-arguing evidence the four analysts
already agreed on. The gate judges whether genuine tension exists and decides
with a LangGraph ``Command``: into the debate (``Bull Researcher``) or straight
past it (``Research Manager``).

Skip-caution is the whole contract (#1176 class): a skip hands the Research
Manager a run with no conflicting arguments, so the gate only skips on an
explicit aligned verdict with confidence above ``low``. Any failure -- an
exception, a ``None``, an unparseable payload -- logs a WARNING and routes into
the debate, which is exactly today's behavior. There is deliberately no
free-text retry: the decision that matters is only ever taken from a validated
structured verdict, and a failed judge must not cost a second LLM call.
"""

from __future__ import annotations

import logging
from typing import Literal

from langgraph.types import Command

from tradingagents.agents.gate.schemas import (
    DebateGateVerdict,
    render_debate_gate_marker,
)
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    report_or_absent,
)
from tradingagents.agents.utils.structured import NO_EXTERNAL_TOOLS, bind_structured
from tradingagents.dataflows.config import get_config

logger = logging.getLogger(__name__)

DEBATE_GATE_MODES = ("always", "auto", "never")

# The verdict recorded when the gate could not judge: the run took the debate
# path, and downstream surfaces (e02s02) need to say why rather than infer it.
_GATE_FAILURE_VERDICT = "gate-failure: judge unavailable, debate held"


def create_debate_gate(quick_llm) -> Command[Literal["Bull Researcher", "Research Manager"]]:
    """Create the Debate Gate node.

    ``Reason for Depth`` (story e02s01): isolates policy-routing agents from
    evidence-producing agents, and the same factory shape serves the deferred
    risk-debate gate without re-plumbing the graph.

    The ``Command`` target set is a static ``Literal``, and both labels are
    registered nodes in ``GraphSetup.setup_graph`` -- a drifted label would
    otherwise crash LangGraph mid-run (#1088).
    """
    structured_llm = bind_structured(quick_llm, DebateGateVerdict, "Debate Gate")

    def debate_gate_node(state) -> Command[Literal["Bull Researcher", "Research Manager"]]:
        # Read the policy at invocation, not at factory build: the factory is
        # constructed once at graph setup while the mode is a run-time config
        # value (same house pattern as get_language_instruction).
        mode = get_config().get("debate_gate", "auto")

        if mode == "always":
            # The pre-gate behavior, exactly: the debate runs and the judge is
            # never consulted, so this mode can spend nothing.
            return Command(
                update={"debate_gate_verdict": ""},
                goto="Bull Researcher",
            )

        if mode == "never":
            # Degraded-mode switch (#1170): with no judge available to call,
            # every run takes the conservative skip so an aligned run never pays
            # for a debate nobody can arbitrate. The rationale says so rather
            # than presenting the skip as the judge's own finding.
            skipped = DebateGateVerdict(
                evidence_aligned=True,
                confidence="medium",
                aligned_direction="unclear",
                rationale=(
                    "debate_gate is configured to never run the Bull/Bear debate: "
                    "the judge is disabled and the analyst reports are treated as "
                    "uncontested."
                ),
            )
            return _skip(skipped)

        if mode not in DEBATE_GATE_MODES:
            # The graph validates the mode at init, so reaching here means drift.
            # A mode nobody recognises must not silently behave like `auto` and
            # skip a debate: fail toward holding it.
            return _fail_safe(state, ValueError(f"unknown debate_gate mode {mode!r}"))

        if structured_llm is None:
            return _fail_safe(state, "provider does not support structured output")

        market_report = report_or_absent(state["market_report"], "market")
        sentiment_report = report_or_absent(state["sentiment_report"], "sentiment")
        news_report = report_or_absent(state["news_report"], "news")
        fundamentals_report = report_or_absent(
            state["fundamentals_report"], "fundamentals"
        )
        instrument_context = get_instrument_context_from_state(state)

        prompt = f"""You are the Debate Gate for a trading research pipeline. Four analysts have already reported on this instrument; their reports follow.

Decide whether a Bull/Bear debate is still worth holding: does the evidence contain genuine, unresolved tension, or do the reports point the same way?

{instrument_context}

---
Market research report: {market_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
Fundamentals report: {fundamentals_report}
---

Rules:
- Set evidence_aligned true ONLY when the four reports support the same directional conclusion on this instrument.
- Any missing or thin report means confidence "low", and low confidence keeps the debate.
- Name the disagreement in `rationale` when the reports conflict; this text reaches the Research Manager when the debate is skipped.
- You are not making the investment call and not rating the instrument: you are only deciding whether the question is still contested.

{NO_EXTERNAL_TOOLS}"""

        try:
            verdict = structured_llm.invoke(prompt)
            if verdict is None:
                # A thinking model can answer in prose instead of filling the
                # schema; the parser then returns nothing at all. That is not a
                # verdict, so it must not become a skip.
                raise ValueError("structured output returned no parsed result")
        except Exception as exc:
            return _fail_safe(state, exc)

        # Skip only on a strong, directional verdict. `mixed` / `unclear` mean the
        # reports agree on some evidence but not on a call, which is precisely the
        # tension the debate exists to resolve; confidence below `high` means the
        # judge itself is not sure the reports line up.
        if (
            not verdict.evidence_aligned
            or verdict.confidence != "high"
            or verdict.aligned_direction not in ("bullish", "bearish")
        ):
            return Command(
                update={
                    "debate_gate_verdict": render_debate_gate_marker(verdict),
                    "investment_debate_state": _empty_debate_state(),
                },
                goto="Bull Researcher",
            )

        return _skip(verdict)

    return debate_gate_node


def _skip(
    verdict: DebateGateVerdict,
) -> Command[Literal["Bull Researcher", "Research Manager"]]:
    """Route past the debate, handing the Research Manager the alignment marker.

    ``investment_debate_state.history`` is never left empty: the Research
    Manager's prompt reads it, and an empty history is what invites a fabricated
    debate (#1176). The marker states that no debate was held.
    """
    marker = render_debate_gate_marker(verdict)
    logger.info("Debate Gate: skipping the debate -- %s", verdict.rationale)
    return Command(
        update={
            "debate_gate_verdict": marker,
            "investment_debate_state": {
                **_empty_debate_state(),
                "history": marker,
                "current_response": marker,
            },
        },
        goto="Research Manager",
    )


def _fail_safe(
    state, exc: Exception
) -> Command[Literal["Bull Researcher", "Research Manager"]]:
    """Any gate failure degrades to the unconditional behavior: hold the debate."""
    logger.warning(
        "Debate Gate: judge failed (%s); holding the debate for %s",
        exc,
        state.get("company_of_interest", "the instrument"),
    )
    return Command(
        update={"debate_gate_verdict": _GATE_FAILURE_VERDICT},
        goto="Bull Researcher",
    )


def _empty_debate_state() -> dict:
    """A cleared debate transcript for whichever path the gate routes."""
    return {
        "bull_history": "",
        "bear_history": "",
        "history": "",
        "current_response": "",
        "judge_decision": "",
        "count": 0,
    }
