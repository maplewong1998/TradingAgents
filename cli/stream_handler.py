"""Per-chunk updates for the live run view (story e02s02).

The CLI streams ``stream_mode="values"``, so every chunk is the whole state after
one node finished: agent statuses are derived from what the state now contains,
not from the event that produced it. This module owns that mapping and the
analyst-status helpers it uses; ``cli/main.py`` owns the layout and calls
``apply_value_chunk`` once per chunk.

Extracted from ``cli/main.py`` — a CONVENTIONS § File-Size Exceptions row
("MUST NOT grow further") — because the skipped-debate status lands here.
"""

from __future__ import annotations

from tradingagents.graph.analyst_execution import sync_analyst_tracker_from_chunk

# A status of its own, not a flavour of "completed": the gate routed these two
# agents past the debate, so showing them as completed would claim work nobody
# did, and leaving them pending would read as a stalled run (SC-e02s02-P2-01).
SKIPPED = "skipped"

# Ordered list of analysts for status transitions
ANALYST_ORDER = ["market", "social", "news", "fundamentals"]
ANALYST_AGENT_NAMES = {
    "market": "Market Analyst",
    "social": "Sentiment Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
}
ANALYST_REPORT_MAP = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}

_RESEARCH_TEAM = ("Bull Researcher", "Bear Researcher", "Research Manager")
_DEBATERS = ("Bull Researcher", "Bear Researcher")


def apply_value_chunk(message_buffer, chunk, wall_time_tracker=None) -> None:
    """Advance the live view by one ``values`` chunk of the run."""
    update_analyst_statuses(message_buffer, chunk, wall_time_tracker)
    _apply_research_team(message_buffer, chunk)
    _apply_trading_team(message_buffer, chunk)
    _apply_risk_team(message_buffer, chunk)


def debate_was_skipped(debate: dict) -> bool:
    """Whether this chunk shows the gate having routed past the debate.

    The discriminator is the debate transcript, never ``debate_gate_verdict``:
    the held path writes that key too (``agents/gate/debate_gate.py``, the
    ``Command`` into the Bull Researcher), and the marker it writes is the same
    sentence on both sides, so neither its presence nor its text can tell a skip
    from a held debate. What only a skip does is hand the Research Manager a
    non-empty ``history`` with no Bull/Bear transcript and no rounds played
    (``_skip`` / ``_skip_by_policy``).
    """
    if str(debate.get("bull_history") or "").strip():
        return False
    if str(debate.get("bear_history") or "").strip():
        return False
    if int(debate.get("count") or 0) > 0:
        return False
    return bool(str(debate.get("history") or "").strip())


def update_research_team_status(message_buffer, status) -> None:
    """Update status for research team members (not Trader)."""
    for agent in _RESEARCH_TEAM:
        message_buffer.update_agent_status(agent, status)


def update_analyst_statuses(message_buffer, chunk, wall_time_tracker=None) -> None:
    """Update analyst statuses based on accumulated report state.

    Logic:
    - Store new report content from the current chunk if present
    - Check accumulated report_sections (not just current chunk) for status
    - Analysts with reports = completed
    - First analyst without report = in_progress
    - Remaining analysts without reports = pending
    - When all analysts done, set Bull Researcher to in_progress
    """
    selected = message_buffer.selected_analysts
    found_active = False

    if wall_time_tracker is not None:
        sync_analyst_tracker_from_chunk(wall_time_tracker, chunk)

    for analyst_key in ANALYST_ORDER:
        if analyst_key not in selected:
            continue

        agent_name = ANALYST_AGENT_NAMES[analyst_key]
        report_key = ANALYST_REPORT_MAP[analyst_key]

        # Capture new report content from current chunk
        if chunk.get(report_key):
            message_buffer.update_report_section(report_key, chunk[report_key])

        # Determine status from accumulated sections, not just current chunk
        has_report = bool(message_buffer.report_sections.get(report_key))

        if has_report:
            message_buffer.update_agent_status(agent_name, "completed")
        elif not found_active:
            message_buffer.update_agent_status(agent_name, "in_progress")
            found_active = True
        else:
            message_buffer.update_agent_status(agent_name, "pending")

    # When all analysts complete, transition research team to in_progress
    if (
        not found_active
        and selected
        and message_buffer.agent_status.get("Bull Researcher") == "pending"
    ):
        message_buffer.update_agent_status("Bull Researcher", "in_progress")


def _apply_research_team(message_buffer, chunk) -> None:
    debate = chunk.get("investment_debate_state")
    if not debate:
        return

    bull_hist = str(debate.get("bull_history") or "").strip()
    bear_hist = str(debate.get("bear_history") or "").strip()
    judge = str(debate.get("judge_decision") or "").strip()

    if debate_was_skipped(debate):
        for agent in _DEBATERS:
            message_buffer.update_agent_status(agent, SKIPPED)
    elif bull_hist or bear_hist:
        # Only update status when there's actual content
        update_research_team_status(message_buffer, "in_progress")

    if bull_hist:
        message_buffer.update_report_section(
            "investment_plan", f"### Bull Researcher Analysis\n{bull_hist}"
        )
    if bear_hist:
        message_buffer.update_report_section(
            "investment_plan", f"### Bear Researcher Analysis\n{bear_hist}"
        )
    if judge:
        message_buffer.update_report_section(
            "investment_plan", f"### Research Manager Decision\n{judge}"
        )
        # A held debate finished for the debaters; a skipped one did not, and
        # "skipped" is terminal for those two (SC-e02s02-P2-01).
        for agent in _DEBATERS:
            if message_buffer.agent_status.get(agent) != SKIPPED:
                message_buffer.update_agent_status(agent, "completed")
        message_buffer.update_agent_status("Research Manager", "completed")
        message_buffer.update_agent_status("Trader", "in_progress")


def _apply_trading_team(message_buffer, chunk) -> None:
    if chunk.get("trader_investment_plan"):
        message_buffer.update_report_section(
            "trader_investment_plan", chunk["trader_investment_plan"]
        )
        if message_buffer.agent_status.get("Trader") != "completed":
            message_buffer.update_agent_status("Trader", "completed")
            message_buffer.update_agent_status("Aggressive Analyst", "in_progress")


def _apply_risk_team(message_buffer, chunk) -> None:
    risk_state = chunk.get("risk_debate_state")
    if not risk_state:
        return

    agg_hist = str(risk_state.get("aggressive_history") or "").strip()
    con_hist = str(risk_state.get("conservative_history") or "").strip()
    neu_hist = str(risk_state.get("neutral_history") or "").strip()
    judge = str(risk_state.get("judge_decision") or "").strip()

    for history, agent in (
        (agg_hist, "Aggressive Analyst"),
        (con_hist, "Conservative Analyst"),
        (neu_hist, "Neutral Analyst"),
    ):
        if history:
            if message_buffer.agent_status.get(agent) != "completed":
                message_buffer.update_agent_status(agent, "in_progress")
            message_buffer.update_report_section(
                "final_trade_decision", f"### {agent} Analysis\n{history}"
            )
    if judge and message_buffer.agent_status.get("Portfolio Manager") != "completed":
        message_buffer.update_agent_status("Portfolio Manager", "in_progress")
        message_buffer.update_report_section(
            "final_trade_decision", f"### Portfolio Manager Decision\n{judge}"
        )
        for agent in ("Aggressive Analyst", "Conservative Analyst", "Neutral Analyst"):
            message_buffer.update_agent_status(agent, "completed")
        message_buffer.update_agent_status("Portfolio Manager", "completed")


def settle_agent_statuses(message_buffer) -> None:
    """Mark the run's agents finished, leaving a skipped debate skipped.

    Called once the stream ends. Overwriting "skipped" with "completed" here
    would re-claim the debate the gate routed past.
    """
    for agent, status in list(message_buffer.agent_status.items()):
        if status != SKIPPED:
            message_buffer.update_agent_status(agent, "completed")
